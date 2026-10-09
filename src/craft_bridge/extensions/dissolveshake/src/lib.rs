//! Original bounded two-image shake/dissolve. Not Sapphire code or equivalence.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 43;
const MAX_PIXELS: usize = 8_388_608;
type Pixel = [f32; 4];
#[derive(Clone, Copy)]
struct Geometry {
    offset: [f64; 2],
    scale: f64,
    size: [f64; 2],
}
struct Image {
    pixels: Vec<Pixel>,
    w: usize,
    h: usize,
    geo: Geometry,
}
fn zeros<T: Clone + Default>(n: usize) -> Result<Vec<T>, ()> {
    let mut v = Vec::new();
    v.try_reserve_exact(n).map_err(|_| ())?;
    v.resize(n, T::default());
    Ok(v)
}
fn valid(p: &[f64], time: f64, scale: f64, timing: [f64; 4]) -> bool {
    p.len() == FLAT
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (1. / 65536. ..=16.).contains(&scale)
        && timing.iter().all(|v| v.is_finite())
        && (0.001..=1e6).contains(&timing[0])
        && timing[1].abs() <= 1e9
        && timing[2].abs() <= 1e9
        && (1e-9..=1e9).contains(&timing[3])
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 | 1 => v.fract() == 0. && (0. ..=u32::MAX as f64).contains(&v),
                    2 | 12 | 13 | 42 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    3 | 4 | 9 => v == 0. || v == 1.,
                    5 | 10 => (0. ..=100.).contains(&v),
                    6 => (1. ..=10000.).contains(&v),
                    11 => (0. ..=1e9).contains(&v),
                    18 | 23 | 28 | 33 | 37..=39 => (-1e6..=1e6).contains(&v),
                    _ => (0. ..=10000.).contains(&v),
                }
        })
}
fn progress(p: &[f64], time: f64, timing: [f64; 4]) -> f64 {
    if p[4] == 0. {
        (p[5] / 100.).clamp(0., 1.)
    } else if timing[1] == timing[2] {
        1.
    } else {
        ((time - timing[1]) / (timing[2] - timing[1])).clamp(0., 1.)
    }
}
fn blend(u: f64, speed: f64) -> f64 {
    ((u - 0.5) * speed + 0.5).clamp(0., 1.)
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
    (n >> 11) as f64 * (2. / (1u64 << 53) as f64) - 1.
}
fn noise(t: f64, seed: u64, stream: u64) -> f64 {
    let n = t.floor() as i64;
    let u = t - t.floor();
    let s = u * u * u * (u * (u * 6. - 15.) + 10.);
    let a = random(n, seed, stream);
    a + (random(n.wrapping_add(1), seed, stream) - a) * s
}
fn motion(p: &[f64], time: f64, channel: usize, u: f64) -> [f64; 4] {
    let t = time + p[37 + channel];
    let seed = p[11].to_bits();
    std::array::from_fn(|axis| {
        let base = 14 + axis * 5;
        let phase = t + p[base + 4];
        let stream = axis as u64 + 1;
        let rand = noise(phase * p[8] * p[base + 1], seed, stream);
        let wave = (std::f64::consts::TAU * (phase * p[8] * p[base + 3]).rem_euclid(1.)).sin();
        let rgb = p[40]
            * noise(
                phase * p[8] * p[41],
                seed,
                stream + 100 * (channel as u64 + 1),
            );
        p[7] * p[34 + channel] * (4. * u * (1. - u)) * (p[base] * (rand + rgb) + p[base + 2] * wave)
    })
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
fn coordinate(v: f64, size: usize, mode: u8) -> Option<f64> {
    if !v.is_finite() {
        return None;
    }
    if mode == 0 {
        if v < -1. || v >= size as f64 {
            None
        } else {
            Some(v)
        }
    } else {
        Some(v.rem_euclid(size as f64 * if mode == 1 { 1. } else { 2. }))
    }
}
fn sample(image: Option<&Image>, point: [f64; 2], wrap: [u8; 2], opacity: f64) -> [f64; 4] {
    let Some(img) = image else {
        return [0.; 4];
    };
    let Some(x) = coordinate(
        point[0] * img.geo.scale + img.geo.offset[0] - 0.5,
        img.w,
        wrap[0],
    ) else {
        return [0.; 4];
    };
    let Some(y) = coordinate(
        point[1] * img.geo.scale + img.geo.offset[1] - 0.5,
        img.h,
        wrap[1],
    ) else {
        return [0.; 4];
    };
    let ix = x.floor() as i64;
    let iy = y.floor() as i64;
    let fx = x - x.floor();
    let fy = y - y.floor();
    let mut out = [0.; 4];
    for (dx, dy, weight) in [
        (0, 0, (1. - fx) * (1. - fy)),
        (1, 0, fx * (1. - fy)),
        (0, 1, (1. - fx) * fy),
        (1, 1, fx * fy),
    ] {
        if let (Some(x), Some(y)) = (
            wrapped(ix + dx, img.w, wrap[0]),
            wrapped(iy + dy, img.h, wrap[1]),
        ) {
            let px = img.pixels[y * img.w + x];
            for ch in 0..4 {
                let v = if ch == 3 && opacity == 0. {
                    1.
                } else if ch < 3 && opacity == 1. && px[3] == 0. {
                    0.
                } else {
                    px[ch] as f64
                };
                out[ch] += v * weight;
            }
        }
    }
    out
}
fn transformed(point: [f64; 2], geo: Geometry, m: [f64; 4], sign: f64) -> [f64; 2] {
    let cx = geo.size[0] * 0.5;
    let cy = geo.size[1] * 0.5;
    let zoom = (-sign * m[2] / 1000.)
        .clamp(-13.815510557964274, 13.815510557964274)
        .exp();
    let (sin, cos) = (sign * m[3]).rem_euclid(360.).to_radians().sin_cos();
    let dx = point[0] - cx - sign * m[0];
    let dy = point[1] - cy - sign * m[1];
    [
        cx + zoom * (cos * dx + sin * dy),
        cy + zoom * (-sin * dx + cos * dy),
    ]
}
fn render(
    main: &Image,
    bg: Option<&Image>,
    p: &[f64],
    time: f64,
    scale: f64,
    timing: [f64; 4],
) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale, timing) {
        return Err(());
    }
    let samples = if p[9] == 1. && p[10] > 0. { 8 } else { 1 };
    let mut moments = Vec::new();
    for n in 0..samples {
        let t = time
            + if samples == 1 {
                0.
            } else {
                ((n as f64 + 0.5) / samples as f64 - 0.5) * p[10] * timing[3]
            };
        let u = progress(p, t, timing);
        let factor = blend(u, p[6]);
        moments.push((
            std::array::from_fn::<_, 3, _>(|ch| motion(p, t, ch, u)),
            if p[3] == 0. { factor } else { 1. - factor },
        ));
    }
    let mut out: Vec<Pixel> = zeros(main.pixels.len())?;
    for (i, px) in out.iter_mut().enumerate() {
        let point = [
            ((i % main.w) as f64 + 0.5 - main.geo.offset[0]) / main.geo.scale,
            ((i / main.w) as f64 + 0.5 - main.geo.offset[1]) / main.geo.scale,
        ];
        let mut sum = [0.; 4];
        for (motions, factor) in &moments {
            let mut color = [0.; 4];
            for (ch, m) in motions.iter().enumerate() {
                let a = sample(
                    Some(main),
                    transformed(point, main.geo, *m, 1.),
                    [p[12] as u8, p[13] as u8],
                    p[42],
                );
                let b = sample(
                    bg,
                    bg.map_or(point, |img| transformed(point, img.geo, *m, -1.)),
                    [p[12] as u8, p[13] as u8],
                    p[42],
                );
                color[ch] = a[ch] * (1. - factor) + b[ch] * factor;
                color[3] = color[3].max(a[3] * (1. - factor) + b[3] * factor);
            }
            for ch in 0..4 {
                sum[ch] += color[ch];
            }
        }
        *px = sum.map(|v| (v / samples as f64) as f32);
    }
    if out.iter().flatten().any(|v| !v.is_finite()) {
        return Err(());
    }
    Ok(out)
}
fn u32at(data: &[u8], off: usize) -> Result<u32, ()> {
    Ok(u32::from_le_bytes(
        data.get(off..off + 4)
            .ok_or(())?
            .try_into()
            .map_err(|_| ())?,
    ))
}
fn f64at(data: &[u8], off: usize) -> Result<f64, ()> {
    Ok(f64::from_le_bytes(
        data.get(off..off + 8)
            .ok_or(())?
            .try_into()
            .map_err(|_| ())?,
    ))
}
fn image(
    data: &[u8],
    base: usize,
    entry: usize,
    expected: usize,
    decl: u32,
    uid: [u32; 2],
    main: bool,
) -> Result<(Option<Image>, usize), ()> {
    let d = FLAT * 8 + entry * 80;
    if u32at(data, d)? != decl
        || [u32at(data, d + 4)?, u32at(data, d + 8)?] != uid
        || u32at(data, d + 28)? != 0
        || u32at(data, d + 72)? != 0
        || u32at(data, d + 76)? != 0
    {
        return Err(());
    }
    let flag = u32at(data, d + 12)?;
    if !main && uid == [0, 0] {
        if flag != 0
            || data[d + 16..d + 28].iter().any(|v| *v != 0)
            || data[d + 32..d + 72].iter().any(|v| *v != 0)
        {
            return Err(());
        }
        return Ok((None, expected));
    }
    if flag != if main { 1 } else { 2 } || (!main && uid == [0, 0]) {
        return Err(());
    }
    let ptr = u32at(data, d + 16)? as usize;
    let w = u32at(data, d + 20)? as usize;
    let h = u32at(data, d + 24)? as usize;
    let n = w
        .checked_mul(h)
        .filter(|n| *n > 0 && *n <= MAX_PIXELS)
        .ok_or(())?;
    let end = expected
        .checked_add(n * 16)
        .filter(|v| *v <= data.len())
        .ok_or(())?;
    if ptr != base + expected || w > 65536 || h > 65536 {
        return Err(());
    }
    let geo = Geometry {
        offset: [f64at(data, d + 32)?, f64at(data, d + 40)?],
        scale: f64at(data, d + 48)?,
        size: [f64at(data, d + 56)?, f64at(data, d + 64)?],
    };
    if geo.offset.iter().any(|v| !v.is_finite() || v.abs() > 1e9)
        || !geo.scale.is_finite()
        || !(1.0 / 65536.0..=16.0).contains(&geo.scale)
    {
        return Err(());
    }
    for offset in [56, 64] {
        let v = f64at(data, d + offset)?;
        if !v.is_finite() || !(f64::MIN_POSITIVE..=1e9).contains(&v) {
            return Err(());
        }
    }
    let mut pixels: Vec<Pixel> = zeros(n)?;
    for (px, bytes) in pixels
        .iter_mut()
        .zip(data[expected..end].as_chunks::<16>().0)
    {
        for ch in 0..4 {
            px[ch] = f32::from_le_bytes(bytes[ch * 4..ch * 4 + 4].try_into().map_err(|_| ())?);
        }
        if px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&px[3]) {
            return Err(());
        }
    }
    Ok((Some(Image { pixels, w, h, geo }), end))
}
thread_local! {static HOST:RefCell<Vec<u64>>=const{RefCell::new(Vec::new())};}
#[unsafe(no_mangle)]
pub extern "C" fn ec_api_version() -> i32 {
    3
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
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 * 2 + FLAT * 8 + 192 {
        return 0;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let n = (bytes as usize).div_ceil(8);
        let extra = n.saturating_sub(host.len());
        if host.try_reserve(extra).is_err() {
            return 0;
        }
        host.resize(n, 0);
        host.as_mut_ptr() as i32
    })
}
#[unsafe(no_mangle)]
#[allow(clippy::too_many_arguments)]
pub extern "C" fn ec_render_v3(
    pixels: i32,
    w: i32,
    h: i32,
    params: i32,
    nparams: i32,
    time: f64,
    scale: f64,
    table: i32,
    entries: i32,
    timing: i32,
) -> i32 {
    if nparams != FLAT as i32 || entries != 2 || w <= 0 || h <= 0 {
        return 1;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let base = host.as_mut_ptr() as usize;
        if params as u32 as usize != base
            || table as u32 as usize != base + FLAT * 8
            || timing as u32 as usize != base + FLAT * 8 + 160
            || pixels as u32 as usize != base + FLAT * 8 + 192
        {
            return 1;
        }
        let data =
            unsafe { std::slice::from_raw_parts(host.as_ptr() as *const u8, host.len() * 8) };
        let attempt = (|| -> Result<Vec<Pixel>, ()> {
            let mut p = [0.; FLAT];
            for (i, v) in p.iter_mut().enumerate() {
                *v = f64at(data, i * 8)?;
            }
            let mut times = [0.; 4];
            for (i, v) in times.iter_mut().enumerate() {
                *v = f64at(data, FLAT * 8 + 160 + i * 8)?;
            }
            if !valid(&p, time, scale, times) {
                return Err(());
            }
            let (main, next) = image(data, base, 0, FLAT * 8 + 192, u32::MAX, [0, 0], true)?;
            let main = main.ok_or(())?;
            if main.w != w as usize || main.h != h as usize || main.geo.scale != scale {
                return Err(());
            }
            let (bg, _) = image(data, base, 1, next, 0, [p[0] as u32, p[1] as u32], false)?;
            render(&main, bg.as_ref(), &p, time, scale, times)
        })();
        let Ok(out) = attempt else {
            return 1;
        };
        let dst = unsafe {
            std::slice::from_raw_parts_mut((base + FLAT * 8 + 192) as *mut Pixel, out.len())
        };
        dst.copy_from_slice(&out);
        0
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn defaults() -> [f64; FLAT] {
        [
            0., 0., 0., 0., 0., 0., 3., 3., 10., 0., 0.5, 0., 2., 2., 192., 1., 0., 0.5, 0., 96.,
            1., 0., 0.5, 0., 0., 1., 0., 0.5, 0., 0., 1., 0., 0.5, 0., 1., 1., 1., 0., 0., 0., 0.,
            2., 1.,
        ]
    }
    fn img(px: Pixel, w: usize, h: usize) -> Image {
        Image {
            pixels: vec![px; w * h],
            w,
            h,
            geo: Geometry {
                offset: [0., 0.],
                scale: 1.,
                size: [w as f64, h as f64],
            },
        }
    }
    const TIMING: [f64; 4] = [30., 0., 1., 1. / 30.];
    #[test]
    fn dissolve_endpoints_speed_and_direction() {
        let a = img([1., 0., 0., 1.], 3, 2);
        let b = img([0., 1., 0., 1.], 3, 2);
        let mut p = defaults();
        p[7] = 0.;
        for (percent, expected) in [
            (0., [1., 0., 0., 1.]),
            (25., [1., 0., 0., 1.]),
            (50., [0.5, 0.5, 0., 1.]),
            (75., [0., 1., 0., 1.]),
            (100., [0., 1., 0., 1.]),
        ] {
            p[5] = percent;
            assert_eq!(
                render(&a, Some(&b), &p, 0., 1., TIMING).unwrap()[0],
                expected
            );
        }
        p[3] = 1.;
        p[5] = 0.;
        assert_eq!(render(&a, Some(&b), &p, 0., 1., TIMING).unwrap(), b.pixels);
        p[6] = 1.;
        p[5] = 25.;
        assert_eq!(
            render(&a, Some(&b), &p, 0., 1., TIMING).unwrap()[0],
            [0.25, 0.75, 0., 1.]
        );
    }
    #[test]
    fn auto_uses_actual_first_last_frames_and_reverse() {
        let mut p = defaults();
        p[4] = 1.;
        let times = [24., 0.25, 1.25, 1. / 24.];
        assert_eq!(progress(&p, 0.25, times), 0.);
        assert_eq!(progress(&p, 0.75, times), 0.5);
        assert_eq!(progress(&p, 1.25, times), 1.);
        let times = [24., 1.25, 0.25, 1. / 24.];
        assert_eq!(progress(&p, 0.75, times), 0.5);
        assert_eq!(progress(&p, 1.25, times), 0.);
        assert_eq!(progress(&p, 0.25, [24., 0.25, 0.25, 1. / 24.]), 1.);
    }
    #[test]
    fn envelope_preserves_both_endpoints_even_with_shake() {
        let p = defaults();
        assert_eq!(motion(&p, 0.23, 0, 0.), [0.; 4]);
        assert_eq!(motion(&p, 0.23, 0, 1.), [0.; 4]);
        assert_ne!(motion(&p, 0.23, 0, 0.5), [0.; 4]);
    }
    #[test]
    fn fractional_seed_and_time_determinism() {
        let p = defaults();
        let m = motion(&p, 0.23, 0, 0.5);
        assert_eq!(m, motion(&p, 0.23, 0, 0.5));
        assert_ne!(m, motion(&p, 0.24, 0, 0.5));
        let mut q = p;
        q[11] = 0.103;
        assert_ne!(m, motion(&q, 0.23, 0, 0.5));
    }
    #[test]
    fn geometry_and_wrap_handle_different_images() {
        let mut b = img([1., 0., 0., 1.], 2, 1);
        b.geo.offset = [1., 0.];
        assert_eq!(sample(Some(&b), [0.5, 0.5], [0, 0], 1.), [1., 0., 0., 1.]);
        assert_eq!(sample(Some(&b), [2.5, 0.5], [0, 0], 1.), [0.; 4]);
        assert_eq!(sample(Some(&b), [2.5, 0.5], [1, 1], 1.), [1., 0., 0., 1.]);
        assert_eq!(sample(Some(&b), [1e30, 1e30], [2, 2], 1.), [1., 0., 0., 1.]);
        b.geo.offset = [0., 0.];
        b.geo.scale = 0.5;
        assert_eq!(sample(Some(&b), [1., 1.], [0, 0], 1.), [1., 0., 0., 1.]);
    }
    #[test]
    fn exact_wave_translation_and_zoom_rotation() {
        let mut p = defaults();
        p[7] = 1.;
        p[8] = 1.;
        p[14] = 0.;
        p[19] = 0.;
        p[16] = 1.;
        p[17] = 1.;
        let m = motion(&p, 0.25, 0, 0.5);
        assert!((m[0] - 1.).abs() < 1e-10);
        let geo = img([1.; 4], 3, 1).geo;
        assert_eq!(transformed([1.5, 0.5], geo, m, 1.), [0.5, 0.5]);
        let z = transformed([2.5, 0.5], geo, [0., 0., 1000. * 2f64.ln(), 0.], 1.);
        assert!((z[0] - 2.).abs() < 1e-10);
        let rotated = transformed([2.5, 0.5], geo, [0., 0., 0., 90.], 1.);
        assert!((rotated[0] - 1.5).abs() < 1e-10 && (rotated[1] + 0.5).abs() < 1e-10);
    }
    #[test]
    fn spatial_motion_blur_uses_actual_frame_step() {
        let a = Image {
            pixels: (0..9).map(|i| [i as f32 / 10., 0., 0., 1.]).collect(),
            w: 9,
            h: 1,
            geo: Geometry {
                offset: [0., 0.],
                scale: 1.,
                size: [9., 1.],
            },
        };
        let mut p = defaults();
        p[5] = 50.;
        p[6] = 1.;
        p[14] = 0.;
        p[19] = 0.;
        p[16] = 2.;
        p[17] = 1.;
        p[8] = 1.;
        p[9] = 1.;
        p[10] = 10.;
        p[12] = 1.;
        let x = render(&a, None, &p, 0.25, 1., [30., 0., 1., 1. / 30.]).unwrap();
        let y = render(&a, None, &p, 0.25, 1., [60., 0., 1., 1. / 60.]).unwrap();
        assert_ne!(x, y);
    }
    #[test]
    fn channel_separation_changes_each_rgb_path() {
        let mut p = defaults();
        p[7] = 1.;
        p[8] = 1.;
        p[14] = 0.;
        p[19] = 0.;
        p[16] = 1.;
        p[17] = 1.;
        p[34] = 0.;
        assert_eq!(motion(&p, 0.25, 0, 0.5), [0.; 4]);
        assert_ne!(motion(&p, 0.25, 1, 0.5), [0.; 4]);
        p[38] = 0.25;
        assert!((motion(&p, 0.25, 1, 0.5)[0]).abs() < 1e-10);
    }
    #[test]
    fn alpha_modes_and_explicit_null_background() {
        let a = img([1., 0., 0., 1.], 2, 2);
        let mut p = defaults();
        p[7] = 0.;
        p[5] = 50.;
        p[6] = 1.;
        assert_eq!(
            render(&a, None, &p, 0., 1., TIMING).unwrap()[0],
            [0.5, 0., 0., 0.5]
        );
        let hidden = img([1., 1., 1., 0.], 1, 1);
        p[5] = 0.;
        assert_eq!(
            render(&hidden, None, &p, 0., 1., TIMING).unwrap()[0],
            [0.; 4]
        );
        p[42] = 2.;
        assert_eq!(
            render(&hidden, None, &p, 0., 1., TIMING).unwrap()[0],
            [1., 1., 1., 0.]
        );
        p[42] = 0.;
        assert_eq!(
            render(&hidden, None, &p, 0., 1., TIMING).unwrap()[0],
            [1.; 4]
        );
    }
    #[test]
    fn invalid_parameters_and_timing_rejected() {
        let a = img([1.; 4], 1, 1);
        let mut p = defaults();
        p[3] = 0.5;
        assert!(render(&a, None, &p, 0., 1., TIMING).is_err());
        p = defaults();
        p[5] = 101.;
        assert!(render(&a, None, &p, 0., 1., TIMING).is_err());
        p = defaults();
        assert!(render(&a, None, &p, f64::NAN, 1., TIMING).is_err());
        assert!(render(&a, None, &p, 0., 1., [0., 0., 1., 0.]).is_err());
    }
    #[test]
    fn extreme_bounded_coefficients_stay_finite() {
        let a = img([2., -1., 0.25, 0.5], 3, 2);
        let b = img([0.5, 0.5, 1., 0.5], 2, 1);
        let mut p = defaults();
        p[5] = 50.;
        p[7] = 10000.;
        p[8] = 10000.;
        p[14] = 10000.;
        p[24] = 10000.;
        p[29] = 10000.;
        p[40] = 10000.;
        p[9] = 1.;
        p[10] = 100.;
        assert!(
            render(&a, Some(&b), &p, 1e9, 1., [0.001, -1e9, 1e9, 1e9])
                .unwrap()
                .iter()
                .flatten()
                .all(|v| v.is_finite())
        );
    }
}
