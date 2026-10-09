//! Original mathematical compositor. Independent calibration, not Sapphire code.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 21;
const MAX_PIXELS: usize = 8_388_608;
type Pixel = [f32; 4];

#[derive(Clone, Copy)]
struct Geometry {
    offset: [f64; 2],
    scale: f64,
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
fn valid(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (1.0 / 65536.0..=16.0).contains(&scale)
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 | 1 | 3 | 4 => v.fract() == 0.0 && (0.0..=u32::MAX as f64).contains(&v),
                    2 | 5 | 17 => v.fract() == 0.0 && (0.0..=2.0).contains(&v),
                    6 => v.fract() == 0.0 && (0.0..=16.0).contains(&v),
                    7 | 18 | 20 => v == 0.0 || v == 1.0,
                    9 | 12 | 15 => (-64.0..=64.0).contains(&v),
                    19 => (0.0..=8192.0).contains(&v),
                    _ => (0.0..=64.0).contains(&v),
                }
        })
}
fn clean(v: f64) -> f64 {
    v.clamp(-1e6, 1e6)
}
fn luma(v: [f64; 3]) -> f64 {
    0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
}
fn adjust(mut v: [f64; 3], p: &[f64]) -> [f64; 3] {
    for ch in &mut v {
        *ch = clean(*ch * (p[0] - p[1]) + p[1]);
    }
    let y = luma(v);
    std::array::from_fn(|ch| clean(y + (v[ch] - y) * p[2]))
}
fn colors(v: Pixel, normal: bool) -> [f64; 3] {
    std::array::from_fn(|ch| {
        clean(if normal {
            if v[3] > 0.0 {
                v[ch] as f64 / v[3] as f64
            } else {
                0.0
            }
        } else {
            v[ch] as f64
        })
    })
}
fn math(a: f64, b: f64, op: usize) -> f64 {
    clean(match op {
        0 => a + b,
        1 => a - b,
        2 => a * b,
        3 => {
            if b.abs() < 1e-12 {
                0.0
            } else {
                a / b
            }
        }
        4 => a + b - a * b,
        5 => (a + b) * 0.5,
        6 => {
            if b <= 0.5 {
                2.0 * a * b
            } else {
                1.0 - 2.0 * (1.0 - a) * (1.0 - b)
            }
        }
        7 => a.min(b),
        8 => a.max(b),
        9 => (a - b).abs(),
        10 => a + b - 2.0 * a * b,
        11..=13 => {
            let x = (a.clamp(0.0, 1.0) * 255.0).round() as u8;
            let y = (b.clamp(0.0, 1.0) * 255.0).round() as u8;
            (match op {
                11 => x ^ y,
                12 => x & y,
                _ => x | y,
            }) as f64
                / 255.0
        }
        14 => {
            if b.abs() < 1e-12 {
                0.0
            } else {
                a.rem_euclid(b.abs())
            }
        }
        15 => {
            if b.abs() < 1e-12 {
                0.0
            } else {
                (a / b.abs()).round() * b.abs()
            }
        }
        16 => {
            if b.abs() < 1e-12 {
                0.0
            } else {
                let t = a.rem_euclid(2.0 * b.abs());
                b.abs() - (t - b.abs()).abs()
            }
        }
        _ => unreachable!(),
    })
}
fn sample(image: Option<&Image>, layer: [f64; 2]) -> Pixel {
    let Some(img) = image else {
        return [0.0; 4];
    };
    // Pixel centers transformed through each buffer's documented geometry.
    let x = layer[0] * img.geo.scale + img.geo.offset[0] - 0.5;
    let y = layer[1] * img.geo.scale + img.geo.offset[1] - 0.5;
    if x < -1.0 || y < -1.0 || x >= img.w as f64 || y >= img.h as f64 {
        return [0.0; 4];
    }
    let ix = x.floor() as isize;
    let iy = y.floor() as isize;
    let fx = x - ix as f64;
    let fy = y - iy as f64;
    let mut out = [0.0f64; 4];
    for (dx, wx) in [(0, 1.0 - fx), (1, fx)] {
        for (dy, wy) in [(0, 1.0 - fy), (1, fy)] {
            let xx = ix + dx;
            let yy = iy + dy;
            if xx >= 0 && yy >= 0 && xx < img.w as isize && yy < img.h as isize {
                let px = img.pixels[yy as usize * img.w + xx as usize];
                for ch in 0..4 {
                    out[ch] += px[ch] as f64 * wx * wy;
                }
            }
        }
    }
    out.map(|v| v as f32)
}
fn box_axis(src: &[f64], dst: &mut [f64], w: usize, h: usize, r: f64, horizontal: bool) {
    let n = r.floor() as isize;
    let f = r - n as f64;
    let (len, lines, step) = if horizontal { (w, h, 1) } else { (h, w, w) };
    for line in 0..lines {
        let base = if horizontal { line * w } else { line };
        let at = |x: isize| src[base + x.clamp(0, len as isize - 1) as usize * step];
        let mut sum =
            at(0) * (n + 1) as f64 + at(len as isize - 1) * (n - (len as isize - 1)).max(0) as f64;
        for x in 1..=n.min(len as isize - 1) {
            sum += at(x);
        }
        for x in 0..len {
            dst[base + x * step] =
                (sum + f * (at(x as isize - n - 1) + at(x as isize + n + 1))) / (2.0 * r + 1.0);
            sum += at(x as isize + n + 1) - at(x as isize - n);
        }
    }
}
fn render(
    main: &Image,
    b: Option<&Image>,
    mask: Option<&Image>,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale) {
        return Err(());
    }
    let normal = p[17] == 1.0;
    let mut matte: Vec<f64> = zeros(main.pixels.len())?;
    if mask.is_some() {
        for (i, v) in matte.iter_mut().enumerate() {
            let layer = [
                ((i % main.w) as f64 + 0.5 - main.geo.offset[0]) / main.geo.scale,
                ((i / main.w) as f64 + 0.5 - main.geo.offset[1]) / main.geo.scale,
            ];
            let px = sample(mask, layer);
            *v = if p[18] == 1.0 {
                px[3] as f64
            } else {
                luma(colors(px, true)) * px[3] as f64
            }
            .clamp(0.0, 1.0);
        }
        let mut tmp: Vec<f64> = zeros(matte.len())?;
        box_axis(&matte, &mut tmp, main.w, main.h, p[19] * scale, true);
        box_axis(&tmp, &mut matte, main.w, main.h, p[19] * scale, false);
    } else {
        matte.fill(1.0);
    }
    let mut out: Vec<Pixel> = zeros(main.pixels.len())?;
    for (i, dst) in out.iter_mut().enumerate() {
        let layer = [
            ((i % main.w) as f64 + 0.5 - main.geo.offset[0]) / main.geo.scale,
            ((i / main.w) as f64 + 0.5 - main.geo.offset[1]) / main.geo.scale,
        ];
        let original = main.pixels[i];
        let mut a = original;
        let mut bpx = sample(b, layer);
        if p[7] == 1.0 {
            std::mem::swap(&mut a, &mut bpx);
        }
        let av = adjust(colors(a, normal), &p[8..11]);
        let bv = adjust(colors(bpx, normal), &p[11..14]);
        let rgb = adjust(
            std::array::from_fn(|ch| math(av[ch], bv[ch], p[6] as usize)),
            &p[14..17],
        );
        let alpha = if p[17] == 0.0 {
            1.0
        } else {
            (a[3] as f64 + bpx[3] as f64 - a[3] as f64 * bpx[3] as f64).clamp(0.0, 1.0)
        };
        let amount = if mask.is_some() && p[20] == 1.0 {
            1.0 - matte[i]
        } else {
            matte[i]
        };
        *dst = std::array::from_fn(|ch| {
            let result = if ch == 3 {
                alpha
            } else {
                rgb[ch] * if normal { alpha } else { 1.0 }
            };
            (original[ch] as f64 * (1.0 - amount) + result * amount) as f32
        });
    }
    if out.iter().flatten().any(|v| !v.is_finite()) {
        return Err(());
    }
    Ok(out)
}
thread_local! {static HOST:RefCell<Vec<u64>>=const {RefCell::new(Vec::new())};}
#[unsafe(no_mangle)]
pub extern "C" fn ec_api_version() -> i32 {
    2
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
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 * 3 + FLAT * 8 + 240 {
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
#[unsafe(no_mangle)]
#[allow(clippy::too_many_arguments)]
pub extern "C" fn ec_render_v2(
    pixels: i32,
    w: i32,
    h: i32,
    params: i32,
    nparams: i32,
    time: f64,
    scale: f64,
    table: i32,
    entries: i32,
) -> i32 {
    if nparams != FLAT as i32 || entries != 3 || w <= 0 || h <= 0 {
        return 1;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let base = host.as_mut_ptr() as usize;
        if params as u32 as usize != base
            || table as u32 as usize != base + FLAT * 8
            || pixels as u32 as usize != base + FLAT * 8 + 240
        {
            return 1;
        }
        // Only parse the checked allocation; copy images before committing any pixels.
        let data =
            unsafe { std::slice::from_raw_parts(host.as_ptr() as *const u8, host.len() * 8) };
        let attempt = (|| -> Result<Vec<Pixel>, ()> {
            let mut p = [0.0; FLAT];
            for (i, v) in p.iter_mut().enumerate() {
                *v = f64at(data, i * 8)?;
            }
            if !valid(&p, time, scale) {
                return Err(());
            }
            let (main, next) = image(data, base, 0, FLAT * 8 + 240, u32::MAX, [0, 0], true)?;
            let main = main.ok_or(())?;
            if main.w != w as usize || main.h != h as usize || main.geo.scale != scale {
                return Err(());
            }
            let (b, next) = image(data, base, 1, next, 0, [p[0] as u32, p[1] as u32], false)?;
            let (mask, _) = image(data, base, 2, next, 2, [p[3] as u32, p[4] as u32], false)?;
            render(&main, b.as_ref(), mask.as_ref(), &p, time, scale)
        })();
        let Ok(out) = attempt else {
            return 1;
        };
        let dst = unsafe {
            std::slice::from_raw_parts_mut((base + FLAT * 8 + 240) as *mut Pixel, out.len())
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
            0., 0., 0., 0., 0., 0., 0., 0., 1., 0., 1., 1., 0., 1., 1., 0., 1., 1., 0., 0., 0.,
        ]
    }
    fn img(p: Pixel, w: usize, h: usize) -> Image {
        Image {
            pixels: vec![p; w * h],
            w,
            h,
            geo: Geometry {
                offset: [0., 0.],
                scale: 1.,
            },
        }
    }
    #[test]
    fn explicit_two_images_add_and_darks() {
        let mut p = defaults();
        p[9] = -0.04;
        let a = img([0.5, 0., 0., 1.], 2, 2);
        let b = img([0., 0.5, 0., 1.], 2, 2);
        let v = render(&a, Some(&b), None, &p, 0., 1.).unwrap();
        assert!((v[0][0] - 0.48).abs() < 1e-6);
        assert!((v[0][1] - 0.46).abs() < 1e-6);
        assert!((v[0][2] + 0.04).abs() < 1e-6);
    }
    #[test]
    fn operation_reference_values() {
        let a = 0.25;
        let b = 0.5;
        let expected = [
            0.75,
            -0.25,
            0.125,
            0.5,
            0.625,
            0.375,
            0.25,
            0.25,
            0.5,
            0.25,
            0.5,
            192. / 255.,
            0.,
            192. / 255.,
            0.25,
            0.5,
            0.25,
        ];
        for (op, v) in expected.iter().enumerate() {
            assert!((math(a, b, op) - v).abs() < 1e-10, "{op}");
        }
    }
    #[test]
    fn swap_uses_a_controls_after_swap() {
        let a = img([0.2, 0.2, 0.2, 1.], 1, 1);
        let b = img([0.5, 0.5, 0.5, 1.], 1, 1);
        let mut p = defaults();
        p[7] = 1.;
        p[6] = 1.;
        p[8] = 2.;
        let v = render(&a, Some(&b), None, &p, 0., 1.).unwrap();
        assert!((v[0][0] - 0.8).abs() < 1e-6);
    }
    #[test]
    fn mask_black_preserves_input_white_processes() {
        let a = img([0.2, 0.2, 0.2, 1.], 2, 2);
        let b = img([0.3, 0.3, 0.3, 1.], 2, 2);
        let black = img([0., 0., 0., 1.], 2, 2);
        let white = img([1., 1., 1., 1.], 2, 2);
        assert_eq!(
            render(&a, Some(&b), Some(&black), &defaults(), 0., 1.).unwrap(),
            a.pixels
        );
        let out = render(&a, Some(&b), Some(&white), &defaults(), 0., 1.).unwrap();
        assert!((out[0][0] - 0.5).abs() < 1e-6);
    }
    #[test]
    fn geometry_offsets_scale_and_outside() {
        let mut b = img([1., 0., 0., 1.], 2, 1);
        b.geo.offset = [1., 0.];
        assert_eq!(sample(Some(&b), [0.5, 0.5]), [1., 0., 0., 1.]);
        assert_eq!(sample(Some(&b), [2.5, 0.5]), [0.; 4]);
        b.geo.scale = 0.5;
        b.geo.offset = [0., 0.];
        assert_eq!(sample(Some(&b), [1., 1.]), [1., 0., 0., 1.]);
    }
    #[test]
    fn fractional_blur_matches_direct_box() {
        let src = [0., 0., 1., 0., 0.];
        let mut dst = [0.; 5];
        box_axis(&src, &mut dst, 5, 1, 1.5, true);
        assert_eq!(dst, [0.125, 0.25, 0.25, 0.25, 0.125]);
    }
    #[test]
    fn invalid_parameters_and_zero_divisors() {
        let a = img([1., 1., 1., 1.], 1, 1);
        let mut p = defaults();
        p[6] = 0.5;
        assert!(render(&a, None, None, &p, 0., 1.).is_err());
        for op in [3, 14, 15, 16] {
            assert_eq!(math(1., 0., op), 0.);
        }
        p = defaults();
        p[9] = f64::NAN;
        assert!(render(&a, None, None, &p, 0., 1.).is_err());
    }
    #[test]
    fn normal_ignores_hidden_rgb() {
        let a = img([1., 1., 1., 0.], 1, 1);
        assert_eq!(
            render(&a, None, None, &defaults(), 0., 1.).unwrap(),
            vec![[0.; 4]]
        );
    }
    #[test]
    fn all_modes_finite_hdr() {
        let a = img([0.5, -0.25, 0.1, 0.5], 2, 2);
        let b = img([0.1, 0.25, 0.0, 0.25], 2, 2);
        for op in 0..17 {
            for opacity in 0..3 {
                let mut p = defaults();
                p[6] = op as f64;
                p[17] = opacity as f64;
                let v = render(&a, Some(&b), None, &p, 0., 1.).unwrap();
                assert!(v.iter().flatten().all(|x| x.is_finite()));
            }
        }
    }
    #[test]
    fn mask_blur_spreads_an_impulse_and_inversion_complements() {
        let a = img([0., 0., 0., 1.], 5, 1);
        let b = img([1., 1., 1., 1.], 5, 1);
        let mut mask = img([0., 0., 0., 1.], 5, 1);
        mask.pixels[2] = [1.; 4];
        let mut p = defaults();
        p[19] = 1.5;
        let out = render(&a, Some(&b), Some(&mask), &p, 0., 1.).unwrap();
        let expected = [0.125, 0.25, 0.25, 0.25, 0.125];
        for (px, value) in out.iter().zip(expected) {
            assert!((px[0] - value).abs() < 1e-6);
        }
        p[20] = 1.;
        let inv = render(&a, Some(&b), Some(&mask), &p, 0., 1.).unwrap();
        for (x, y) in out.iter().zip(inv) {
            assert!((x[0] + y[0] - 1.).abs() < 1e-6);
        }
    }
    #[test]
    fn alpha_modes_have_explicit_independent_models() {
        let a = img([0.25, 0., 0., 0.5], 1, 1);
        let b = img([0., 0.125, 0., 0.25], 1, 1);
        let mut p = defaults();
        assert_eq!(
            render(&a, Some(&b), None, &p, 0., 1.).unwrap()[0],
            [0.3125, 0.3125, 0., 0.625]
        );
        p[17] = 2.;
        assert_eq!(
            render(&a, Some(&b), None, &p, 0., 1.).unwrap()[0],
            [0.25, 0.125, 0., 0.625]
        );
        p[17] = 0.;
        assert_eq!(
            render(&a, Some(&b), None, &p, 0., 1.).unwrap()[0],
            [0.25, 0.125, 0., 1.]
        );
    }
    #[test]
    fn descriptor_rejects_alias_nan_pixels_and_reserved_bits() {
        let base = 4096usize;
        let expected = FLAT * 8 + 240;
        let mut bytes = vec![0u8; expected + 16];
        let d = FLAT * 8;
        for (offset, value) in [
            (0, u32::MAX),
            (12, 1),
            (16, (base + expected) as u32),
            (20, 1),
            (24, 1),
        ] {
            bytes[d + offset..d + offset + 4].copy_from_slice(&value.to_le_bytes());
        }
        for offset in [48, 56, 64] {
            bytes[d + offset..d + offset + 8].copy_from_slice(&1f64.to_le_bytes());
        }
        for ch in 0..4 {
            bytes[expected + ch * 4..expected + ch * 4 + 4].copy_from_slice(&1f32.to_le_bytes());
        }
        assert!(image(&bytes, base, 0, expected, u32::MAX, [0, 0], true).is_ok());
        let mut bad = bytes.clone();
        bad[d + 16..d + 20].copy_from_slice(&(base as u32).to_le_bytes());
        assert!(image(&bad, base, 0, expected, u32::MAX, [0, 0], true).is_err());
        let mut bad = bytes.clone();
        bad[expected..expected + 4].copy_from_slice(&f32::NAN.to_le_bytes());
        assert!(image(&bad, base, 0, expected, u32::MAX, [0, 0], true).is_err());
        bytes[d + 72] = 1;
        assert!(image(&bytes, base, 0, expected, u32::MAX, [0, 0], true).is_err());
    }
}
