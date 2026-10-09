//! Original bounded temporal RGB flicker for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 021.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 14;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;

// These bounds describe this original renderer, not proprietary source units.
fn valid(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (1.0 / MAX_SIDE as f64..=16.0).contains(&scale)
        && p.iter().enumerate().all(|(i, v)| match i {
            3 | 5 => (0.0..=10000.0).contains(v),
            6..=8 => v.abs() <= 1e6,
            13 => (0.0..=1e9).contains(v),
            _ => (0.0..=1000.0).contains(v),
        })
}

fn hash(mut x: u64) -> u64 {
    x ^= x >> 30;
    x = x.wrapping_mul(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x = x.wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

fn random(lattice: i64, seed: u64, stream: u64) -> f64 {
    let bits = hash((lattice as u64).wrapping_add(hash(seed ^ stream)));
    (bits >> 11) as f64 * (2.0 / (1u64 << 53) as f64) - 1.0
}

// Stateless C2 interpolation permits arbitrary frame order, subframes and negative time.
fn noise(time: f64, seed: u64, stream: u64) -> f64 {
    let floor = time.floor();
    let u = time - floor;
    let smooth = u * u * u * (u * (u * 6.0 - 15.0) + 10.0);
    let a = random(floor as i64, seed, stream);
    let b = random(floor as i64 + 1, seed, stream);
    a + (b - a) * smooth
}

fn gains(p: &[f64], time: f64) -> [f64; 3] {
    let seed = p[13].to_bits(); // Fractional seeds are never rounded to integers.
    let random_time = time * p[3];
    let luma = p[1] * noise(random_time, seed, 0);
    std::array::from_fn(|ch| {
        // Raw phase is interpreted in cycles here, not inferred source units.
        let phase = (time * p[5] + p[6 + ch]).rem_euclid(1.0);
        let wave = p[4] * (std::f64::consts::TAU * phase).sin();
        let color = p[2] * noise(random_time, seed, ch as u64 + 1);
        (p[12] * (1.0 + p[0] * p[9 + ch] * (luma + color + wave))).max(0.0)
    })
}

fn render(
    pixels: &mut [[f32; 4]],
    width: usize,
    height: usize,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<(), ()> {
    if !valid(p, time, scale)
        || width == 0
        || height == 0
        || width > MAX_SIDE
        || height > MAX_SIDE
        || width.checked_mul(height) != Some(pixels.len())
        || pixels.len() > MAX_PIXELS
        || pixels.iter().any(|px| {
            px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&px[3])
        })
    {
        return Err(());
    }
    let gain = gains(p, time);
    // Validate before every write. This bounded domain cannot overflow float32.
    for px in pixels {
        for ch in 0..3 {
            if gain[ch] != 1.0 {
                px[ch] = (px[ch] as f64 * gain[ch]) as f32;
            }
        }
    }
    Ok(())
}

thread_local! {
    static HOST: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) };
}

#[unsafe(no_mangle)]
pub extern "C" fn ec_api_version() -> i32 {
    1
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_ptr() -> i32 {
    MANIFEST.as_ptr() as i32
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_len() -> i32 {
    MANIFEST.len() as i32
}

#[unsafe(no_mangle)]
pub extern "C" fn ec_alloc(bytes: i32) -> i32 {
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 + FLAT_PARAMS * 8 {
        return 0;
    }
    HOST.with(|buf| {
        let mut buf = buf.borrow_mut();
        let additional = (bytes as usize).div_ceil(8).saturating_sub(buf.len());
        if buf.try_reserve(additional).is_err() {
            return 0;
        }
        buf.resize((bytes as usize).div_ceil(8), 0);
        buf.as_mut_ptr() as i32
    })
}

/// The ABI pointers must reference the allocation returned by ec_alloc.
/// Validate both ranges and alignment before forming slices. Invalid calls leave it intact.
#[unsafe(no_mangle)]
pub extern "C" fn ec_render(
    pixels: i32,
    width: i32,
    height: i32,
    params: i32,
    nparams: i32,
    time: f64,
    scale: f64,
) -> i32 {
    if width <= 0 || height <= 0 || nparams != FLAT_PARAMS as i32 {
        return 1;
    }
    let Some(n) = (width as usize)
        .checked_mul(height as usize)
        .filter(|n| *n <= MAX_PIXELS)
    else {
        return 1;
    };
    HOST.with(|buf| {
        let mut buf = buf.borrow_mut();
        let start = buf.as_mut_ptr() as usize;
        let end = start + buf.len() * 8;
        let pp = params as u32 as usize;
        let xp = pixels as u32 as usize;
        if pp != start
            || xp != start + FLAT_PARAMS * 8
            || xp.checked_add(n * 16).is_none_or(|v| v > end)
        {
            return 1;
        }
        // Ranges are aligned, disjoint, inside HOST and the borrow prevents reallocations.
        let p = unsafe { std::slice::from_raw_parts(pp as *const f64, FLAT_PARAMS) };
        let px = unsafe { std::slice::from_raw_parts_mut(xp as *mut [f32; 4], n) };
        match render(px, width as usize, height as usize, p, time, scale) {
            Ok(()) => 0,
            Err(()) => 1,
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> [f64; FLAT_PARAMS] {
        [
            0.2, 1.0, 0.0, 30.0, 0.0, 5.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.123,
        ]
    }
    fn frame(p: &[f64], time: f64) -> Vec<[f32; 4]> {
        let mut image = vec![[0.2, 0.4, 0.1, 0.5]; 4];
        render(&mut image, 2, 2, p, time, 1.0).unwrap();
        image
    }
    fn close(a: f64, b: f64) {
        assert!((a - b).abs() < 1e-6, "{a} != {b}");
    }
    #[test]
    fn zero_amplitude_hdr_identity_and_alpha_exact() {
        let mut p = defaults();
        p[0] = 0.0;
        let mut image = vec![[4.0, -2.0, -0.0, 0.5], [0.3, -0.2, 0.1, 0.0]];
        let before = image.clone();
        render(&mut image, 2, 1, &p, -0.123, 1.0).unwrap();
        assert_eq!(image, before);
        assert_eq!(image[0][2].to_bits(), before[0][2].to_bits());
        p[12] = 2.0;
        render(&mut image, 2, 1, &p, 0.0, 1.0).unwrap();
        assert_eq!(image, vec![[8.0, -4.0, -0.0, 0.5], [0.6, -0.4, 0.2, 0.0]]);
    }
    #[test]
    fn sine_channel_phases_and_amplitude() {
        let mut p = defaults();
        p[0] = 0.5;
        p[1] = 0.0;
        p[4] = 1.0;
        p[5] = 1.0;
        p[7] = 0.25;
        p[8] = 0.5;
        let gain = gains(&p, 0.25);
        close(gain[0], 1.5);
        close(gain[1], 1.0);
        close(gain[2], 0.5);
        assert_eq!(gains(&p, 1.25), gain);
        assert_eq!(gains(&p, -0.75), gain);
        p[9] = 0.0;
        close(gains(&p, 0.25)[0], 1.0);
    }
    #[test]
    fn seed_fraction_and_time_order_deterministic() {
        let p = defaults();
        let first = frame(&p, 0.125);
        assert_ne!(frame(&p, -0.125), first);
        assert_eq!(frame(&p, 0.125), first);
        let mut q = p;
        q[13] += 1e-6;
        assert_ne!(frame(&q, 0.125), first);
        assert_ne!(frame(&p, 0.126), first);
    }
    #[test]
    fn noise_bounded_and_continuous_at_negative_lattice() {
        for t in [-100.5, -3.0, -0.001, 0.0, 0.3, 1e13] {
            assert!((-1.0..=1.0).contains(&noise(t, 11, 2)));
        }
        close(noise(-3.0 - 1e-6, 11, 2), noise(-3.0 + 1e-6, 11, 2));
        assert_ne!(noise(0.33, 11, 0), noise(0.33, 11, 1));
    }
    #[test]
    fn shared_luma_and_independent_color() {
        let mut p = defaults();
        let g = gains(&p, 0.123);
        assert_eq!(g[0], g[1]);
        assert_eq!(g[1], g[2]);
        p[1] = 0.0;
        p[2] = 1.0;
        let g = gains(&p, 0.123);
        assert_ne!(g[0], g[1]);
        assert_ne!(g[1], g[2]);
    }
    #[test]
    fn zero_frequency_and_preview_scale() {
        let mut p = defaults();
        p[3] = 0.0;
        p[5] = 0.0;
        p[4] = 1.0;
        assert_eq!(gains(&p, -100.0), gains(&p, 200.0));
        let mut image = frame(&p, 0.0);
        let mut other = vec![[0.2, 0.4, 0.1, 0.5]; 4];
        render(&mut other, 2, 2, &p, 0.0, 0.25).unwrap();
        assert_eq!(image, other);
        p[12] = 0.0;
        render(&mut image, 2, 2, &p, 0.0, 1.0).unwrap();
        assert!(image.iter().all(|px| *px == [0.0, 0.0, 0.0, 0.5]));
    }
    #[test]
    fn bounded_extremes_and_nonnegative_gain() {
        let mut p = [1000.0; FLAT_PARAMS];
        p[3] = 10000.0;
        p[5] = 10000.0;
        p[13] = 1e9;
        let mut image = vec![[1e6, -1e6, 1e6, 1.0]];
        render(&mut image, 1, 1, &p, 1e9, 1.0).unwrap();
        assert!(image.iter().flatten().all(|v| v.is_finite()));
        p = defaults();
        p[0] = 2.0;
        p[1] = 0.0;
        p[4] = 1.0;
        p[5] = 1.0;
        assert_eq!(gains(&p, 0.75), [0.0; 3]);
    }
    #[test]
    fn invalid_calls_do_not_modify_input() {
        let p = defaults();
        for (i, v) in [
            (0, -0.1),
            (3, 10001.0),
            (6, 1e6 + 1.0),
            (13, 1e9 + 1.0),
            (12, f64::NAN),
        ] {
            let mut q = p;
            q[i] = v;
            let mut image = vec![[1.0; 4]];
            assert!(render(&mut image, 1, 1, &q, 0.0, 1.0).is_err());
            assert_eq!(image, vec![[1.0; 4]]);
        }
        for (time, scale) in [
            (f64::NAN, 1.0),
            (1e9 + 1.0, 1.0),
            (0.0, 0.0),
            (0.0, f64::MIN_POSITIVE),
        ] {
            let mut image = vec![[1.0; 4]];
            assert!(render(&mut image, 1, 1, &p, time, scale).is_err());
            assert_eq!(image, vec![[1.0; 4]]);
        }
        let mut image = vec![[1.0; 4], [1.0, 1.0, 1.0, -0.1]];
        let before = image.clone();
        assert!(render(&mut image, 2, 1, &p, 0.0, 1.0).is_err());
        assert_eq!(image, before);
        assert!(render(&mut image, MAX_SIDE + 1, 1, &p, 0.0, 1.0).is_err());
    }
    #[test]
    fn abi_rejects_foreign_pointer_and_wrong_count() {
        assert_eq!(ec_render(0, 1, 1, 0, FLAT_PARAMS as i32, 0.0, 1.0), 1);
        assert_eq!(ec_render(0, 1, 1, 0, FLAT_PARAMS as i32 - 1, 0.0, 1.0), 1);
        assert_eq!(ec_alloc(-1), 0);
        assert_eq!(ec_alloc((MAX_PIXELS * 16 + FLAT_PARAMS * 8 + 1) as i32), 0);
    }
}
