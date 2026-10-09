//! Original noise heat displacement and spatial blur. Independent of Universe code.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 30;
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
fn valid(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (1.0 / 65536.0..=16.0).contains(&scale)
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 | 1 => v.fract() == 0. && (0. ..=u32::MAX as f64).contains(&v),
                    2 | 3 | 15 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    16 => v.fract() == 0. && (0. ..=3.).contains(&v),
                    17 | 24 => v == 0. || v == 1.,
                    28 => v.fract() == 0. && (0. ..=4.).contains(&v),
                    4 | 7 | 9 | 13 => (0. ..=100.).contains(&v),
                    5 => v.abs() <= 1e6,
                    6 | 12 | 23 => v.abs() <= 10000.,
                    18..=21 | 26 | 27 => v.abs() <= 1e9,
                    29 => v.abs() <= 100.,
                    _ => (0. ..=10000.).contains(&v),
                }
        })
}
fn smooth(x: f64) -> f64 {
    let x = x.clamp(0., 1.);
    x * x * (3. - 2. * x)
}
fn hash(x: i64, y: i64) -> f64 {
    let mut n =
        (x as u64).wrapping_mul(0x9e3779b97f4a7c15) ^ (y as u64).wrapping_mul(0xbf58476d1ce4e5b9);
    n ^= n >> 30;
    n = n.wrapping_mul(0xbf58476d1ce4e5b9);
    n ^= n >> 27;
    n = n.wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 31;
    (n >> 11) as f64 / ((1u64 << 53) - 1) as f64
}
fn noise(x: f64, y: f64) -> f64 {
    let (ix, iy) = (x.floor() as i64, y.floor() as i64);
    let (a, b) = (smooth(x - x.floor()), smooth(y - y.floor()));
    let top = hash(ix, iy) * (1. - a) + hash(ix + 1, iy) * a;
    let bottom = hash(ix, iy + 1) * (1. - a) + hash(ix + 1, iy + 1) * a;
    top * (1. - b) + bottom * b
}
fn field(point: [f64; 2], time: f64, p: &[f64], dim: f64, blur: bool) -> f64 {
    let (size, detail, ds) = if blur {
        (p[11], p[13], p[14])
    } else {
        (p[8], p[9], p[10])
    };
    let size = (size / 100. * dim).max(0.25);
    let freq = (ds / 100.).max(0.01);
    let (sin, cos) = p[5].rem_euclid(360.).to_radians().sin_cos();
    let drift = time * p[6] / 100.;
    let (x, y) = (point[0] / size - drift * cos, point[1] / size - drift * sin);
    let detail = detail / 100.;
    let n = (noise(x, y)
        + detail * noise(x * freq + 17.3, y * freq + 29.7)
        + detail * 0.5 * noise(x * freq * 2. + 51.1, y * freq * 2. - 19.2))
        / (1. + detail * 1.5);
    match p[3] as usize {
        0 => 2. * n - 1.,
        1 => 2. * (2. * n - 1.).abs() - 1.,
        _ => 1. - 2. * (2. * n - 1.).abs(),
    }
}
fn sample(image: Option<&Image>, point: [f64; 2]) -> Pixel {
    let Some(img) = image else { return [0.; 4] };
    let (x, y) = (
        point[0] * img.geo.scale + img.geo.offset[0] - 0.5,
        point[1] * img.geo.scale + img.geo.offset[1] - 0.5,
    );
    if x < -1. || y < -1. || x >= img.w as f64 || y >= img.h as f64 {
        return [0.; 4];
    }
    let (ix, iy) = (x.floor() as isize, y.floor() as isize);
    let (fx, fy) = (x - x.floor(), y - y.floor());
    let mut out = [0.; 4];
    for (dx, wx) in [(0, 1. - fx), (1, fx)] {
        for (dy, wy) in [(0, 1. - fy), (1, fy)] {
            let (xx, yy) = (ix + dx, iy + dy);
            if xx >= 0 && yy >= 0 && xx < img.w as isize && yy < img.h as isize {
                for (ch, value) in out.iter_mut().enumerate() {
                    *value += img.pixels[yy as usize * img.w + xx as usize][ch] as f64 * wx * wy;
                }
            }
        }
    }
    out.map(|x| x as f32)
}
fn point(p: &[f64], i: usize, geo: Geometry) -> [f64; 2] {
    [
        (p[i] - geo.offset[0]) / geo.scale,
        (p[i + 1] - geo.offset[1]) / geo.scale,
    ]
}
fn mask_at(main: &Image, mask: Option<&Image>, q: [f64; 2], p: &[f64]) -> f64 {
    if p[16] == 0. {
        return 1.;
    }
    let dim = main.geo.size[0].min(main.geo.size[1]);
    let value = if p[16] == 3. {
        if p[25] == 0. {
            0.
        } else {
            let pos = point(p, 26, main.geo);
            let k = p[25] / 100.;
            let size = mask.map(|i| i.geo.size).unwrap_or([0.; 2]);
            let v = sample(
                mask,
                [
                    (q[0] - pos[0]) / k + size[0] / 2.,
                    (q[1] - pos[1]) / k + size[1] / 2.,
                ],
            );
            if p[24] == 1. {
                v[3] as f64
            } else {
                (0.2126 * v[0] as f64 + 0.7152 * v[1] as f64 + 0.0722 * v[2] as f64) * v[3] as f64
            }
        }
    } else {
        let a = point(p, 18, main.geo);
        let b = point(p, 20, main.geo);
        let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
        let length = dx.hypot(dy);
        let (ex, ey) = if length > 1e-12 {
            (dx / length, dy / length)
        } else {
            (0., 1.)
        };
        let (x, y) = (q[0] - (a[0] + b[0]) / 2., q[1] - (a[1] + b[1]) / 2.);
        let (along, across) = (x * ex + y * ey, -x * ey + y * ex);
        let radius = p[22] / 100. * dim;
        let half = (length / 2.).max(0.25);
        if radius == 0. {
            0.
        } else {
            let distance = if p[16] == 1. {
                ((along / half).hypot(across / radius) - 1.) * half.min(radius)
            } else {
                (along.abs() - half).max(across.abs() - radius)
            };
            let feather = p[23] / 100. * dim;
            if feather == 0. {
                f64::from(distance <= 0.)
            } else {
                smooth((feather.max(0.) - distance) / feather.abs())
            }
        }
    }
    .clamp(0., 1.);
    if p[17] == 1. { 1. - value } else { value }
}
fn render(
    main: &Image,
    mask: Option<&Image>,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale) {
        return Err(());
    }
    let dim = main.geo.size[0].min(main.geo.size[1]);
    let mut out: Vec<Pixel> = zeros(main.pixels.len())?;
    let side = p[15] as usize + 2;
    for (i, pixel) in out.iter_mut().enumerate() {
        let q = [
            ((i % main.w) as f64 + 0.5 - main.geo.offset[0]) / main.geo.scale,
            ((i / main.w) as f64 + 0.5 - main.geo.offset[1]) / main.geo.scale,
        ];
        let nx = field(q, time, p, dim, false);
        let ny = field([q[0] + 37.3 * dim, q[1] - 13.1 * dim], time, p, dim, false);
        let map = 0.5 + 0.5 * field(q, time, p, dim, true);
        let feather = (p[12].abs() / 1000.).clamp(1e-6, 0.5);
        let map = smooth((map - 0.5 + feather) / (2. * feather));
        let m = mask_at(main, mask, q, p);
        let original = main.pixels[i];
        *pixel = match p[28] as usize {
            1 => [(nx * 0.5 + 0.5) as f32, (ny * 0.5 + 0.5) as f32, 0., 1.],
            2 => {
                let v = (map * m) as f32;
                [v, v, v, 1.]
            }
            3 => [m as f32, m as f32, m as f32, 1.],
            4 => {
                let mix = m * 0.3;
                [
                    (original[0] as f64 * (1. - mix) + mix) as f32,
                    (original[1] as f64 * (1. - mix)) as f32,
                    (original[2] as f64 * (1. - mix) + mix) as f32,
                    original[3],
                ]
            }
            _ => {
                if m == 0. || (p[4] == 0. && p[7] == 0.) {
                    original
                } else {
                    let strength = (1. - p[29] / 100.).max(0.);
                    let intensity = p[4] / 100. * dim * 0.25 * strength;
                    let pos = [q[0] + nx * intensity, q[1] + ny * intensity];
                    let radius = p[7] / 100. * dim * 0.1 * map * strength;
                    let mut blurred = [0.; 4];
                    if radius == 0. {
                        blurred = sample(Some(main), pos).map(f64::from)
                    } else {
                        for y in 0..side {
                            for x in 0..side {
                                let tap = sample(
                                    Some(main),
                                    [
                                        pos[0]
                                            + ((x as f64 + 0.5) / side as f64 - 0.5) * 2. * radius,
                                        pos[1]
                                            + ((y as f64 + 0.5) / side as f64 - 0.5) * 2. * radius,
                                    ],
                                );
                                for ch in 0..4 {
                                    blurred[ch] += tap[ch] as f64 / (side * side) as f64;
                                }
                            }
                        }
                    }
                    std::array::from_fn(|ch| {
                        (original[ch] as f64 * (1. - m) + blurred[ch] * m) as f32
                    })
                }
            }
        };
    }
    if out.iter().flatten().all(|v| v.is_finite()) {
        Ok(out)
    } else {
        Err(())
    }
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
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 * 2 + FLAT * 8 + 160 {
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
    if nparams != FLAT as i32 || entries != 2 || w <= 0 || h <= 0 {
        return 1;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let base = host.as_mut_ptr() as usize;
        if params as u32 as usize != base
            || table as u32 as usize != base + FLAT * 8
            || pixels as u32 as usize != base + FLAT * 8 + 160
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
            if !valid(&p, time, scale) {
                return Err(());
            }
            let (main, next) = image(data, base, 0, FLAT * 8 + 160, u32::MAX, [0, 0], true)?;
            let main = main.ok_or(())?;
            if main.w != w as usize || main.h != h as usize || main.geo.scale != scale {
                return Err(());
            }
            let (bg, _) = image(data, base, 1, next, 0, [p[0] as u32, p[1] as u32], false)?;
            render(&main, bg.as_ref(), &p, time, scale)
        })();
        let Ok(out) = attempt else {
            return 1;
        };
        let dst = unsafe {
            std::slice::from_raw_parts_mut((base + FLAT * 8 + 160) as *mut Pixel, out.len())
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
            0., 0., 0., 0., 25., 90., 19., 25., 100., 42., 150., 100., 100., 42., 50., 0., 0., 0.,
            8., 2., 8., 6., 25., 10., 0., 100., 8., 4., 0., 0.,
        ]
    }
    fn image(w: usize, h: usize) -> Image {
        let pixels = (0..w * h)
            .map(|i| {
                [
                    (i % w) as f32 / w as f32,
                    (i / w) as f32 / h as f32,
                    0.25,
                    1.,
                ]
            })
            .collect();
        Image {
            pixels,
            w,
            h,
            geo: Geometry {
                offset: [0.; 2],
                scale: 1.,
                size: [w as f64, h as f64],
            },
        }
    }
    #[test]
    fn identity_and_full_bias_are_exact() {
        let main = image(16, 8);
        let mut p = defaults();
        p[4] = 0.;
        p[7] = 0.;
        assert_eq!(render(&main, None, &p, 0.3, 1.).unwrap(), main.pixels);
        p[4] = 25.;
        p[7] = 40.;
        p[29] = 100.;
        assert_eq!(render(&main, None, &p, 0.3, 1.).unwrap(), main.pixels);
    }
    #[test]
    fn noise_wave_modes_and_detail_are_bounded_and_distinct() {
        let mut p = defaults();
        let q = [3.2, 6.7];
        let n = field(q, 0.7, &p, 8., false);
        p[3] = 1.;
        let b = field(q, 0.7, &p, 8., false);
        p[3] = 2.;
        let r = field(q, 0.7, &p, 8., false);
        assert!((r + b).abs() < 1e-12);
        assert_ne!(n, b);
        assert!([n, b, r].iter().all(|x| x.abs() <= 1.));
        p[9] = 0.;
        assert_ne!(r, field(q, 0.7, &p, 8., false));
        assert_eq!(noise(-1., 2.), hash(-1, 2));
        assert!((noise(-1. + 1e-8, 2.) - noise(-1. - 1e-8, 2.)).abs() < 1e-7);
    }
    #[test]
    fn spatial_controls_and_direction_change_nonuniform_frames() {
        let main = image(16, 8);
        let p = defaults();
        let baseline = render(&main, None, &p, 0.3, 1.).unwrap();
        for (index, value) in [
            (3, 1.),
            (4, 50.),
            (5, 0.),
            (6, 90.),
            (7, 60.),
            (8, 40.),
            (9, 0.),
            (10, 30.),
            (11, 40.),
            (12, 500.),
            (13, 0.),
            (14, 300.),
            (15, 2.),
            (29, -30.),
        ] {
            let mut changed = p;
            changed[index] = value;
            assert_ne!(
                render(&main, None, &changed, 0.3, 1.).unwrap(),
                baseline,
                "control {index}"
            );
        }
    }
    #[test]
    fn temporal_field_does_not_freeze_and_zero_speed_is_static() {
        let main = image(16, 8);
        let mut p = defaults();
        assert_ne!(
            render(&main, None, &p, 0., 1.).unwrap(),
            render(&main, None, &p, 1., 1.).unwrap()
        );
        p[6] = 0.;
        assert_eq!(
            render(&main, None, &p, 0., 1.).unwrap(),
            render(&main, None, &p, 1., 1.).unwrap()
        );
    }
    #[test]
    fn geometric_masks_hard_feathered_rotated_and_degenerate() {
        let main = image(16, 8);
        let mut p = defaults();
        p[16] = 1.;
        p[23] = 0.;
        assert_eq!(mask_at(&main, None, [8., 4.], &p), 1.);
        assert_eq!(mask_at(&main, None, [11., 4.], &p), 0.);
        p[23] = 10.;
        assert!(mask_at(&main, None, [10.4, 4.], &p) > 0.);
        p[23] = -10.;
        assert!(mask_at(&main, None, [9.5, 4.], &p) < 1.);
        p[23] = 0.;
        p[16] = 2.;
        assert_eq!(mask_at(&main, None, [9.8, 5.8], &p), 1.);
        p[16] = 1.;
        assert_eq!(mask_at(&main, None, [9.8, 5.8], &p), 0.);
        p[18] = 6.;
        p[19] = 4.;
        p[20] = 10.;
        p[21] = 4.;
        assert_eq!(mask_at(&main, None, [8., 4.], &p), 1.);
        p[22] = 0.;
        assert_eq!(mask_at(&main, None, [8., 4.], &p), 0.);
        p[22] = 25.;
        p[20] = p[18];
        p[21] = p[19];
        assert!(mask_at(&main, None, [6., 4.], &p).is_finite());
    }
    #[test]
    fn layer_mask_channel_position_scale_and_null() {
        let main = image(16, 8);
        let mut mask = image(2, 2);
        mask.pixels = vec![[1., 0., 0., 0.5]; 4];
        let mut p = defaults();
        p[16] = 3.;
        assert!((mask_at(&main, Some(&mask), [8., 4.], &p) - 0.1063).abs() < 1e-6);
        p[24] = 1.;
        assert_eq!(mask_at(&main, Some(&mask), [8., 4.], &p), 0.5);
        assert_eq!(mask_at(&main, None, [8., 4.], &p), 0.);
        p[17] = 1.;
        assert_eq!(mask_at(&main, None, [8., 4.], &p), 1.);
        p[17] = 0.;
        p[25] = 50.;
        assert_eq!(mask_at(&main, Some(&mask), [9., 4.], &p), 0.);
        p[26] = 9.;
        assert_eq!(mask_at(&main, Some(&mask), [9., 4.], &p), 0.5);
        p[25] = 0.;
        assert_eq!(mask_at(&main, Some(&mask), [9., 4.], &p), 0.);
    }
    #[test]
    fn mask_geometry_uses_buffer_offset_and_scale() {
        let mut main = image(8, 4);
        main.geo = Geometry {
            offset: [-2., 3.],
            scale: 0.5,
            size: [16., 8.],
        };
        let mut p = defaults();
        p[16] = 1.;
        p[23] = 0.;
        p[18] = 2.;
        p[19] = 4.;
        p[20] = 2.;
        p[21] = 6.;
        assert_eq!(mask_at(&main, None, [8., 4.], &p), 1.);
        assert_eq!(mask_at(&main, None, [13., 4.], &p), 0.);
    }
    #[test]
    fn outputs_diagnostics_and_mask_overlay_follow_mask() {
        let main = image(16, 8);
        let mut p = defaults();
        p[16] = 3.;
        p[28] = 3.;
        let out = render(&main, None, &p, 0., 1.).unwrap();
        assert!(out.iter().all(|v| *v == [0., 0., 0., 1.]));
        p[28] = 4.;
        assert_eq!(render(&main, None, &p, 0., 1.).unwrap(), main.pixels);
        p[16] = 0.;
        p[28] = 3.;
        assert!(
            render(&main, None, &p, 0., 1.)
                .unwrap()
                .iter()
                .all(|v| *v == [1.; 4])
        );
        let mut alternatives = Vec::new();
        for output in 0..5 {
            p[28] = output as f64;
            alternatives.push(render(&main, None, &p, 0.4, 1.).unwrap());
        }
        assert!(alternatives.windows(2).all(|v| v[0] != v[1]));
    }
    #[test]
    fn mask_preserves_pixels_outside_processing() {
        let main = image(16, 8);
        let mut p = defaults();
        p[16] = 1.;
        p[23] = 0.;
        let out = render(&main, None, &p, 0.3, 1.).unwrap();
        assert_eq!(out[0], main.pixels[0]);
        assert_ne!(out[4 * 16 + 8], main.pixels[4 * 16 + 8]);
        p[16] = 3.;
        assert_eq!(render(&main, None, &p, 0.3, 1.).unwrap(), main.pixels);
    }
    #[test]
    fn blur_quality_has_distinct_spatial_sampling() {
        let mut main = image(16, 8);
        main.pixels = vec![[0., 0., 0., 1.]; 128];
        main.pixels[4 * 16 + 8] = [1.; 4];
        let mut p = defaults();
        p[4] = 0.;
        p[7] = 100.;
        p[12] = 500.;
        let first = render(&main, None, &p, 0.3, 1.).unwrap();
        p[15] = 1.;
        let second = render(&main, None, &p, 0.3, 1.).unwrap();
        p[15] = 2.;
        let third = render(&main, None, &p, 0.3, 1.).unwrap();
        assert_ne!(first, second);
        assert_ne!(second, third);
    }
    #[test]
    fn invalid_and_extreme_inputs_do_not_publish_nonfinite_pixels() {
        let main = image(16, 8);
        let p = defaults();
        for (index, value) in [
            (3, 3.),
            (16, 4.),
            (24, 2.),
            (28, 5.),
            (4, 101.),
            (25, -1.),
            (18, f64::NAN),
        ] {
            let mut bad = p;
            bad[index] = value;
            assert!(render(&main, None, &bad, 0., 1.).is_err());
        }
        assert!(render(&main, None, &p, f64::NAN, 1.).is_err());
        let mut extreme = p;
        extreme[18] = 1e9;
        extreme[20] = -1e9;
        extreme[6] = 10000.;
        extreme[16] = 1.;
        extreme[12] = 0.;
        extreme[8] = 0.;
        extreme[10] = 0.;
        assert!(
            render(&main, None, &extreme, 1e9, 1.)
                .unwrap()
                .iter()
                .flatten()
                .all(|v| v.is_finite())
        );
    }
}
