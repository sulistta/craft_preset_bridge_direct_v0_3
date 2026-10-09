//! Original approximate camera shake for EffectCraft API v1. See docs/decisions/010.
//! This implements the Bridge's formula, not proprietary Sapphire code.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 43;
const MAX_PIXELS: usize = 8_388_608;

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

// The manifest's order is the official flattened API layout. These bounds are the
// original renderer's audited operating domain, not inferred Sapphire constraints.
fn parameters_valid(p: &[f64], time: f64, scale: f64) -> bool {
    if p.len() != FLAT_PARAMS
        || p.iter().any(|x| !x.is_finite())
        || !time.is_finite()
        || time.abs() > 1e9
        || !scale.is_finite()
        || !(0.0..=16.0).contains(&scale)
        || scale == 0.0
    {
        return false;
    }
    p.iter().enumerate().all(|(i, &v)| match i {
        0 | 8 | 9 | 42 => [0.0, 1.0, 2.0].contains(&v),
        5 => [0.0, 1.0].contains(&v),
        3 | 14 | 19 | 24 | 29 | 37 | 38 | 39 => v.abs() <= 1e6,
        4 => (0.001..=10000.0).contains(&v),
        6 => (0.0..=100.0).contains(&v),
        7 => (0.0..=1e9).contains(&v),
        30 | 32 | 33 => (0.0..=1.0).contains(&v),
        _ => (0.0..=10000.0).contains(&v),
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
    let n = hash((lattice as u64).wrapping_add(hash(seed ^ stream)));
    (n >> 11) as f64 * (2.0 / (1u64 << 53) as f64) - 1.0
}
fn smooth(t: f64) -> f64 {
    t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
}
fn noise(t: f64, seed: u64, stream: u64, style: u8, drift: f64, bias: f64) -> f64 {
    let n = t.floor() as i64;
    let u = t - t.floor();
    let mut a = random(n, seed, stream);
    let mut b = random(n + 1, seed, stream);
    if style == 2 {
        // Original jump-and-drift: deterministic chance of returning to the center.
        if (random(n, seed, stream + 1000) + 1.0) * 0.5 < bias {
            a = 0.0;
        }
        if (random(n + 1, seed, stream + 1000) + 1.0) * 0.5 < bias {
            b = 0.0;
        }
        a + (b - a) * drift * u
    } else {
        a + (b - a) * smooth(u)
    }
}

fn motion(p: &[f64], time: f64, channel: Option<usize>) -> [f64; 4] {
    let seed = p[7].to_bits(); // fractional source seeds remain distinct
    let t = time + p[3] + channel.map_or(0.0, |c| p[37 + c]);
    let style = p[0] as u8;
    let mut gate = 1.0;
    if style == 1 {
        let u = (t * p[31]).rem_euclid(1.0);
        // Smooth ramps within the moving interval; Stillness=1 stays still.
        if p[30] >= 1.0 || u < p[30] {
            gate = 0.0;
        } else {
            let v = (u - p[30]) / (1.0 - p[30]);
            gate = (std::f64::consts::PI * v).sin().powi(2);
        }
    }
    let amp = p[1] * gate * channel.map_or(1.0, |c| p[34 + c]);
    let mut result = [0.0; 4];
    for (axis, out) in result.iter_mut().enumerate() {
        let base = 10 + axis * 5;
        let stream = axis as u64 + 1;
        let phase = t + p[base + 4];
        let rand = noise(
            phase * p[2] * p[base + 1],
            seed,
            stream,
            style,
            p[32],
            p[33],
        );
        let wave = (std::f64::consts::TAU * (phase * p[2] * p[base + 3]).rem_euclid(1.0)).sin();
        let rgb = channel.map_or(0.0, |c| {
            p[40]
                * noise(
                    phase * p[2] * p[41],
                    seed,
                    stream + 100 * (c as u64 + 1),
                    style,
                    p[32],
                    p[33],
                )
        });
        *out = amp * (p[base] * (rand + rgb) + p[base + 2] * wave);
    }
    result
}

#[derive(Clone, Copy)]
struct Transform {
    a: f64,
    b: f64,
    tx: f64,
    ty: f64,
}
fn transform(p: &[f64], time: f64, channel: Option<usize>, scale: f64) -> Transform {
    let [x, y, z, tilt] = motion(p, time, channel);
    // Own calibration: raw X/Y controls as buffer offsets; raw Z / 1000 in a
    // bounded logarithmic zoom. No claim that these are Sapphire source units.
    let distance = p[4]
        * (-z / 1000.0)
            .clamp(-13.815510557964274, 13.815510557964274)
            .exp();
    let (sin, cos) = tilt.rem_euclid(360.0).to_radians().sin_cos();
    Transform {
        a: distance * cos,
        b: distance * sin,
        tx: x * scale,
        ty: y * scale,
    }
}

fn wrapped(i: i64, size: usize, mode: u8) -> Option<usize> {
    let n = size as i64;
    if i >= 0 && i < n {
        return Some(i as usize);
    }
    match mode {
        0 => None,
        1 => Some(i.rem_euclid(n) as usize),
        _ => {
            let j = i.rem_euclid(n * 2);
            Some(if j < n { j } else { n * 2 - 1 - j } as usize)
        }
    }
}
fn sample(input: &[[f32; 4]], w: usize, h: usize, x: f64, y: f64, wx: u8, wy: u8) -> [f64; 4] {
    let ix = x.floor() as i64;
    let iy = y.floor() as i64;
    let fx = x - x.floor();
    let fy = y - y.floor();
    let mut out = [0.0; 4];
    for (dx, dy, weight) in [
        (0, 0, (1.0 - fx) * (1.0 - fy)),
        (1, 0, fx * (1.0 - fy)),
        (0, 1, (1.0 - fx) * fy),
        (1, 1, fx * fy),
    ] {
        if let (Some(x), Some(y)) = (wrapped(ix + dx, w, wx), wrapped(iy + dy, h, wy)) {
            for (value, source) in out.iter_mut().zip(input[y * w + x]) {
                *value += source as f64 * weight;
            }
        }
    }
    out
}
fn transformed(
    input: &[[f32; 4]],
    w: usize,
    h: usize,
    x: f64,
    y: f64,
    tr: Transform,
    wrap: [u8; 2],
) -> [f64; 4] {
    let cx = (w as f64 - 1.0) * 0.5;
    let cy = (h as f64 - 1.0) * 0.5;
    let dx = x - cx - tr.tx;
    let dy = y - cy - tr.ty;
    sample(
        input,
        w,
        h,
        cx + tr.a * dx + tr.b * dy,
        cy - tr.b * dx + tr.a * dy,
        wrap[0],
        wrap[1],
    )
}
fn render(
    pixels: &mut [[f32; 4]],
    w: usize,
    h: usize,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<(), ()> {
    if !parameters_valid(p, time, scale)
        || w.checked_mul(h) != Some(pixels.len())
        || w == 0
        || h == 0
        || pixels.len() > MAX_PIXELS
        || pixels.iter().any(|px| {
            px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&px[3])
        })
    {
        return Err(());
    }
    let mut input = Vec::new();
    input.try_reserve_exact(pixels.len()).map_err(|_| ())?;
    input.extend_from_slice(pixels);
    if p[42] == 0.0 {
        for px in &mut input {
            px[3] = 1.0;
        }
    }
    let samples = if p[5] == 1.0 && p[6] > 0.0 { 8 } else { 1 };
    let separate =
        p[34..37].iter().any(|&v| v != 1.0) || p[37..40].iter().any(|&v| v != 0.0) || p[40] != 0.0;
    let transforms: Vec<[Transform; 3]> = (0..samples)
        .map(|i| {
            let t = time
                + if samples == 1 {
                    0.0
                } else {
                    ((i as f64 + 0.5) / samples as f64 - 0.5) * p[6] / 30.0
                };
            std::array::from_fn(|c| transform(p, t, if separate { Some(c) } else { None }, scale))
        })
        .collect();
    for (i, pixel) in pixels.iter_mut().enumerate() {
        let x = (i % w) as f64;
        let y = (i / w) as f64;
        let mut sum = [0.0; 4];
        for tr in &transforms {
            let mut color = transformed(&input, w, h, x, y, tr[0], [p[8] as u8, p[9] as u8]);
            if separate {
                for c in 1..3 {
                    let part = transformed(&input, w, h, x, y, tr[c], [p[8] as u8, p[9] as u8]);
                    color[c] = part[c];
                    color[3] = color[3].max(part[3]);
                }
            }
            for c in 0..4 {
                sum[c] += color[c];
            }
        }
        *pixel = sum.map(|v| (v / samples as f64) as f32);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> [f64; 43] {
        [
            0., 1., 8., 0., 1., 0., 1., 0., 2., 2., 192., 1., 0., 0.5, 0., 96., 1., 0., 0.5, 0.,
            0., 1., 0., 0.5, 0., 0., 1., 0., 0.5, 0., 0.7, 2., 0.3, 0., 1., 1., 1., 0., 0., 0., 0.,
            2., 1.,
        ]
    }
    #[test]
    fn identity_and_hdr_premultiplied_alpha() {
        let mut p = defaults();
        p[1] = 0.;
        let input = vec![[2., 1., 0.5, 0.5], [0., 0., 0., 0.], [0.25, 0.5, 0.75, 1.]];
        let mut px = input.clone();
        render(&mut px, 3, 1, &p, 2., 1.).unwrap();
        assert_eq!(px, input);
    }
    #[test]
    fn waves_translation_wrap_and_preview_scale() {
        let mut p = defaults();
        p[2] = 1.;
        p[10] = 0.;
        p[15] = 0.;
        p[12] = 1.;
        p[13] = 1.;
        p[8] = 1.;
        let input = vec![[1., 0., 0., 1.], [0., 1., 0., 1.], [0., 0., 1., 1.]];
        let mut px = input.clone();
        render(&mut px, 3, 1, &p, 0.25, 1.).unwrap();
        assert_eq!(px, vec![input[2], input[0], input[1]]);
        let mut px = input.clone();
        render(&mut px, 3, 1, &p, 0.25, 0.5).unwrap();
        assert_eq!(px[1], [0.5, 0.5, 0., 1.]);
        p[8] = 0.;
        let mut px = input.clone();
        render(&mut px, 3, 1, &p, 0.25, 1.).unwrap();
        assert_eq!(px[0], [0.; 4]);
        p[8] = 2.;
        let mut px = input.clone();
        render(&mut px, 3, 1, &p, 0.25, 1.).unwrap();
        assert_eq!(px[0], input[0]);
    }
    #[test]
    fn hash_time_and_fractional_seed_determinism() {
        let p = defaults();
        assert_eq!(motion(&p, 0.23, None), motion(&p, 0.23, None));
        assert_ne!(motion(&p, 0.23, None), motion(&p, 0.24, None));
        let mut q = p;
        q[7] = 0.25;
        assert_ne!(motion(&p, 0.23, None), motion(&q, 0.23, None));
        q[7] = 0.5;
        assert_ne!(motion(&p, 0.23, None), motion(&q, 0.23, None));
    }
    #[test]
    fn styles_stillness_and_center_bias() {
        let mut p = defaults();
        p[0] = 1.;
        p[30] = 1.;
        assert_eq!(motion(&p, 0.25, None), [0.; 4]);
        p[0] = 2.;
        p[33] = 1.;
        assert_eq!(motion(&p, 0.25, None), [0.; 4]);
        p[33] = 0.;
        p[32] = 0.;
        assert_eq!(motion(&p, 0.001, None), motion(&p, 0.05, None));
        p[32] = 1.;
        assert_ne!(motion(&p, 0.001, None), motion(&p, 0.05, None));
    }
    #[test]
    fn zoom_rotation_channel_separation_and_blur() {
        let mut p = defaults();
        p[10] = 0.;
        p[15] = 0.;
        p[27] = 90.;
        p[28] = 1.;
        p[2] = 1.;
        let input = vec![
            [1., 0., 0., 1.],
            [0., 1., 0., 1.],
            [0., 0., 1., 1.],
            [1., 1., 0., 1.],
        ];
        let mut px = input.clone();
        render(&mut px, 2, 2, &p, 0.25, 1.).unwrap();
        assert!((px[0][0] - input[2][0]).abs() < 1e-6);
        p[27] = 0.;
        p[12] = 1.;
        p[13] = 1.;
        p[34] = 0.;
        let mut px = input.clone();
        render(&mut px, 2, 2, &p, 0.25, 1.).unwrap();
        assert_eq!(px[0][0], 1.);
        p[34] = 1.;
        let mut unblurred = input.clone();
        render(&mut unblurred, 2, 2, &p, 0.25, 1.).unwrap();
        p[5] = 1.;
        let mut blurred = input.clone();
        render(&mut blurred, 2, 2, &p, 0.25, 1.).unwrap();
        assert_ne!(blurred, unblurred);
        p[1] = 0.;
        p[4] = 2.;
        let tr = transform(&p, 0., None, 1.);
        assert_eq!(tr.a, 2.);
    }
    #[test]
    fn invalid_inputs_are_not_modified() {
        let mut p = defaults();
        p[4] = 0.;
        let mut px = vec![[1., 0., 0., 1.]];
        let before = px.clone();
        assert!(render(&mut px, 1, 1, &p, 0., 1.).is_err());
        assert_eq!(px, before);
        p = defaults();
        assert!(render(&mut px, 1, 1, &p, f64::NAN, 1.).is_err());
        assert_eq!(px, before);
        assert!(render(&mut px, 1, 1, &p, 0., 0.).is_err());
        assert_eq!(px, before);
        p[8] = 1.5;
        assert!(render(&mut px, 1, 1, &p, 0., 1.).is_err());
        assert_eq!(px, before);
    }
    #[test]
    fn allocator_and_abi_invalid_ranges_are_safe() {
        assert_eq!(ec_alloc(-1), 0);
        assert_ne!(ec_alloc(43 * 8 + 16), 0);
        assert_eq!(ec_render(0, 1, 1, 0, 43, 0., 1.), 1);
        assert_eq!(ec_render(0, 0, 1, 0, 43, 0., 1.), 1);
        assert_eq!(ec_render(0, 1, 1, 0, 44, 0., 1.), 1);
    }
}
