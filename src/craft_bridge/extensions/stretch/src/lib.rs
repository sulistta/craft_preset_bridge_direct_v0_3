//! Original area-integrated cumulative stretching for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 013.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 20;
const MAX_PIXELS: usize = 8_388_608;
const MAX_SIDE: usize = 65_536;

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
    _time: f64,
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
        match render(px, width as usize, height as usize, p, scale) {
            Ok(()) => 0,
            Err(()) => 1,
        }
    })
}

fn valid(p: &[f64], scale: f64) -> bool {
    if p.len() != FLAT_PARAMS
        || !p.iter().all(|v| v.is_finite())
        || !scale.is_finite()
        || !(0.0..=16.0).contains(&scale)
        || scale == 0.0
    {
        return false;
    }
    for (index, max) in [
        (0, 3),
        (1, 7),
        (5, 5),
        (9, 2),
        (13, 5),
        (16, 1),
        (18, 3),
        (12, 1),
    ] {
        if p[index] < 0.0 || p[index] > max as f64 || p[index] != p[index].floor() {
            return false;
        }
    }
    [
        (2, 0.0, 100.0),
        (3, 0.0, 10000.0),
        (4, 0.001, 10000.0),
        (6, -1e6, 1e6),
        (7, 0.0, 100.0),
        (8, 0.0, 100.0),
        (10, 0.0, 10000.0),
        (11, -1e6, 1e6),
        (14, 0.001, 10000.0),
        (15, -1e6, 1e6),
        (17, 0.0, 100.0),
        (19, 0.0, 100.0),
    ]
    .iter()
    .all(|&(index, lo, hi)| (lo..=hi).contains(&p[index]))
}

fn wave(t: f64, kind: usize) -> f64 {
    match kind {
        0 => t,
        1 => 1.0 - t,
        2 => 1.0 - (2.0 * t - 1.0).abs(),
        3 => 0.5 - 0.5 * (std::f64::consts::TAU * t).cos(),
        4 => t * t,
        5 => (1.0 - t) * (1.0 - t),
        _ => unreachable!(),
    }
}

struct Curve([f64; 1025]);
impl Curve {
    fn new(p: &[f64]) -> Self {
        let phase = (p[6] / 360.0).rem_euclid(1.0);
        let smooth = p[7] / 100.0;
        Self(std::array::from_fn(|i| {
            let t = i as f64 / 1024.0;
            if smooth == 0.0 {
                return wave(
                    if phase == 0.0 {
                        t
                    } else {
                        (t + phase).rem_euclid(1.0)
                    },
                    p[5] as usize,
                );
            }
            // Original periodic nine-tap box, not the source's smoothing kernel.
            (-4..=4)
                .map(|j| {
                    wave(
                        (t + phase + j as f64 * smooth / 8.0).rem_euclid(1.0),
                        p[5] as usize,
                    )
                })
                .sum::<f64>()
                / 9.0
        }))
    }
    fn sample(&self, t: f64) -> f64 {
        let coordinate = t.clamp(0.0, 1.0) * 1024.0;
        let index = (coordinate.floor() as usize).min(1023);
        let fraction = coordinate - index as f64;
        self.0[index] * (1.0 - fraction) + self.0[index + 1] * fraction
    }
}

fn distribution(x: f64, length: usize, p: &[f64]) -> f64 {
    let start = p[8] / 100.0 * length as f64;
    if x < start || p[10] == 0.0 || start >= length as f64 {
        return 0.0;
    }
    let extent = if p[10] > 1.0 {
        length as f64 - start
    } else {
        p[10] * length as f64
    };
    if x >= start + extent {
        return 0.0;
    }
    let t = ((x - start) / extent).clamp(0.0, 1.0);
    match p[9] as usize {
        0 => 1.0,
        1 => t,
        2 => 1.0 - t,
        _ => unreachable!(),
    }
}

fn intensity(pixel: [f64; 4], channel: usize) -> f64 {
    let a = pixel[3];
    if channel == 3 {
        return a;
    }
    if a <= 1e-12 {
        return 0.0;
    }
    if channel < 3 {
        return (pixel[channel] / a).clamp(0.0, 1.0);
    }
    ((0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]) / a).clamp(0.0, 1.0)
}

// Original area reconstruction: an interval has constant premultiplied color.
// Prefix integrals make subpixel footprints independent of stretch amount.
struct Line {
    edges: Vec<f64>,
    sums: Vec<[f64; 4]>,
    values: Vec<[f64; 4]>,
}
fn zeros<T: Clone>(length: usize, value: T) -> Result<Vec<T>, ()> {
    let mut result = Vec::new();
    result.try_reserve_exact(length).map_err(|_| ())?;
    result.resize(length, value);
    Ok(result)
}
fn add(a: [f64; 4], b: [f64; 4]) -> [f64; 4] {
    std::array::from_fn(|i| a[i] + b[i])
}
fn subtract(a: [f64; 4], b: [f64; 4]) -> [f64; 4] {
    std::array::from_fn(|i| a[i] - b[i])
}
fn multiply(a: [f64; 4], value: f64) -> [f64; 4] {
    a.map(|v| v * value)
}

fn edge_index(index: isize, length: usize, mode: usize) -> Option<usize> {
    let n = length as isize;
    match mode {
        0 => Some(index.rem_euclid(n) as usize),
        1 => {
            let x = index.rem_euclid(2 * n);
            Some(if x < n { x } else { 2 * n - 1 - x } as usize)
        }
        2 => Some(index.clamp(0, n - 1) as usize),
        3 => (index >= 0 && index < n).then_some(index as usize),
        _ => unreachable!(),
    }
}
fn point(values: &[[f64; 4]], coordinate: f64, mode: usize) -> [f64; 4] {
    let lo = coordinate.floor();
    let fraction = coordinate - lo;
    let at = |x| edge_index(x, values.len(), mode).map_or([0.0; 4], |i| values[i]);
    add(
        multiply(at(lo as isize), 1.0 - fraction),
        multiply(at(lo as isize + 1), fraction),
    )
}

impl Line {
    fn build(
        values: &[[f64; 4]],
        channel: usize,
        curve: &Curve,
        p: &[f64],
        shift: f64,
    ) -> Result<Self, ()> {
        let n = values.len();
        let mut line = Self {
            edges: zeros(n + 1, 0.0)?,
            sums: zeros(n + 1, [0.0; 4])?,
            values: zeros(n, [0.0; 4])?,
        };
        for i in 0..n {
            let source = if p[12] == 1.0 && shift != 0.0 {
                point(values, i as f64 - shift, p[18] as usize)
            } else {
                values[i]
            };
            let growth = p[4] + p[3] * curve.sample(intensity(source, channel));
            let width = 1.0 + p[2] / 100.0 * distribution(i as f64 + 0.5, n, p) * (growth - 1.0);
            line.edges[i + 1] = line.edges[i] + width;
            line.sums[i + 1] = add(line.sums[i], multiply(values[i], width));
            line.values[i] = values[i];
        }
        Ok(line)
    }
    fn total(&self) -> f64 {
        *self.edges.last().unwrap()
    }
    fn sum(&self) -> [f64; 4] {
        *self.sums.last().unwrap()
    }
    fn prefix(&self, coordinate: f64) -> [f64; 4] {
        if coordinate <= 0.0 {
            return [0.0; 4];
        }
        if coordinate >= self.total() {
            return self.sum();
        }
        let index = self.edges.partition_point(|&edge| edge <= coordinate) - 1;
        add(
            self.sums[index],
            multiply(self.values[index], coordinate - self.edges[index]),
        )
    }
    fn mirrored_prefix(&self, coordinate: f64) -> [f64; 4] {
        let total = self.total();
        if coordinate <= total {
            self.prefix(coordinate)
        } else {
            subtract(
                multiply(self.sum(), 2.0),
                self.prefix(2.0 * total - coordinate),
            )
        }
    }
    fn area(&self, start: f64, end: f64, mode: usize) -> [f64; 4] {
        let total = self.total();
        // Interior footprints need no border arithmetic (including expensive fmod).
        // This is exactly the same prefix integral, not a reduced-quality preview.
        if start >= 0.0 && end <= total {
            return subtract(self.prefix(end), self.prefix(start));
        }
        if mode >= 2 {
            let mut area = subtract(self.prefix(end), self.prefix(start));
            if mode == 2 {
                area = add(
                    area,
                    multiply(self.values[0], (end.min(0.0) - start.min(0.0)).max(0.0)),
                );
                area = add(
                    area,
                    multiply(
                        *self.values.last().unwrap(),
                        (end.max(total) - start.max(total)).max(0.0),
                    ),
                );
            }
            return area;
        }
        let period = if mode == 0 { total } else { 2.0 * total };
        let prefix = |x| {
            if mode == 0 {
                self.prefix(x)
            } else {
                self.mirrored_prefix(x)
            }
        };
        let period_sum = if mode == 0 {
            self.sum()
        } else {
            multiply(self.sum(), 2.0)
        };
        let a = start.rem_euclid(period);
        let length = end - start;
        // Normalize before subtraction: large shifts must not cancel huge integrals.
        let first = length.min(period - a);
        let mut result = subtract(prefix(a + first), prefix(a));
        let remaining = (length - first).max(0.0);
        let cycles = (remaining / period).floor();
        result = add(result, multiply(period_sum, cycles));
        add(
            result,
            prefix((remaining - cycles * period).clamp(0.0, period)),
        )
    }
    fn pixel(&self, coordinate: usize, shift: f64, p: &[f64], length: usize) -> [f64; 4] {
        let x = coordinate as f64 - shift;
        let mut result = self.area(x, x + 1.0, p[18] as usize);
        if p[18] == 3.0 && p[19] > 0.0 {
            let distance = (x + 0.5).min(self.total() - x - 0.5);
            let feather = p[19] / 100.0 * length as f64;
            result = multiply(result, (distance / feather).clamp(0.0, 1.0));
        }
        result
    }
}

fn straight_component(value: [f64; 4], channel: usize) -> f64 {
    if value[3] > 1e-12 {
        value[channel] / value[3]
    } else {
        0.0
    }
}
fn shading(x: usize, p: &[f64], scale: f64) -> f64 {
    if p[13] == 0.0 || p[17] == 0.0 {
        return 1.0;
    }
    let t = (x as f64 / (p[14] * scale) + p[15] / 360.0).rem_euclid(1.0);
    let pattern = match p[13] as usize {
        1 => wave(t, 3),
        2 => wave(t, 2),
        3 => t,
        4 => 1.0 - t,
        5 => {
            if t < 0.1 {
                1.0
            } else {
                0.0
            }
        }
        _ => unreachable!(),
    };
    1.0 - pattern * p[17] / 100.0 * p[2] / 100.0
}

fn render(
    pixels: &mut [[f32; 4]],
    width: usize,
    height: usize,
    p: &[f64],
    scale: f64,
) -> Result<(), ()> {
    if width == 0
        || height == 0
        || width > MAX_SIDE
        || height > MAX_SIDE
        || width.checked_mul(height) != Some(pixels.len())
        || pixels.len() > MAX_PIXELS
        || !valid(p, scale)
        || pixels.iter().any(|v| {
            v.iter().any(|c| !c.is_finite() || c.abs() > 1e6) || !(0.0..=1.0).contains(&v[3])
        })
    {
        return Err(());
    }
    if p[2] == 0.0 || (p[3] == 0.0 && p[4] == 1.0 && p[11] == 0.0 && (p[13] == 0.0 || p[17] == 0.0))
    {
        return Ok(());
    }
    let horizontal = p[0] < 2.0;
    let reverse = [1.0, 3.0].contains(&p[0]);
    let (lines, length, step) = if horizontal {
        (height, width, 1)
    } else {
        (width, height, width)
    };
    let curve = Curve::new(p);
    let mut output = zeros(pixels.len(), [0.0_f32; 4])?;
    let shift = p[11] / 360.0 * length as f64 * p[2] / 100.0;
    let mut values = zeros(length, [0.0_f64; 4])?;
    let mut result = zeros(length, [0.0_f64; 4])?;
    for line in 0..lines {
        let base = if horizontal { line * width } else { line };
        let index = |i| base + if reverse { length - 1 - i } else { i } * step;
        for i in 0..length {
            values[i] = pixels[index(i)].map(|v| v as f64);
            result[i] = values[i];
        }
        let channels = p[1] as usize;
        let passes: &[usize] = match channels {
            0 | 6 => &[4],
            1 => &[0, 1, 2, 3],
            2 => &[0],
            3 => &[1],
            4 => &[2],
            5 => &[3],
            7 => &[0, 1, 2],
            _ => unreachable!(),
        };
        // Keep straight RGB until all channel maps select their output alpha.
        for value in &mut result {
            for c in 0..3 {
                value[c] = straight_component(*value, c);
            }
        }
        for &channel in passes {
            let map = Line::build(&values, channel, &curve, p, shift)?;
            for (i, value) in result.iter_mut().enumerate() {
                let sample = map.pixel(i, shift, p, length);
                if channel == 4 {
                    for (c, component) in value.iter_mut().take(3).enumerate() {
                        *component = straight_component(sample, c);
                    }
                    if channels == 0 {
                        value[3] = sample[3];
                    }
                } else if channel == 3 {
                    value[3] = sample[3];
                } else {
                    value[channel] = straight_component(sample, channel);
                }
            }
        }
        for (i, value) in result.iter_mut().enumerate() {
            value[3] = value[3].clamp(0.0, 1.0);
            for c in 0..3 {
                value[c] *= value[3];
            }
            let shade = shading(i, p, scale);
            if p[16] == 0.0 {
                *value = multiply(*value, shade);
            } else {
                for c in value.iter_mut().take(3) {
                    *c *= shade;
                }
            }
            output[index(i)] = value.map(|v| v.clamp(-1e6, 1e6) as f32);
        }
    }
    pixels.copy_from_slice(&output);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn params() -> [f64; FLAT_PARAMS] {
        [
            0., 0., 100., 0., 1., 0., 0., 0., 0., 0., 2., 0., 1., 0., 10., 0., 0., 0., 0., 0.,
        ]
    }
    fn grayscale(v: f32) -> [f32; 4] {
        [v, v, v, 1.]
    }
    fn near(a: &[f32; 4], b: &[f32; 4]) {
        for (a, b) in a.iter().zip(b) {
            assert!((a - b).abs() < 1e-6, "{a} vs {b}");
        }
    }
    #[test]
    fn brightness_stretch_accumulates_and_subpixel_area_is_preserved() {
        let mut p = params();
        p[3] = 1.;
        let mut pixels = vec![grayscale(0.), grayscale(1.), grayscale(0.5), grayscale(0.)];
        render(&mut pixels, 4, 1, &p, 1.).unwrap();
        // Segment widths are exactly 1, 2, 1.5 and 1.
        assert_eq!(
            pixels,
            vec![grayscale(0.), grayscale(1.), grayscale(1.), grayscale(0.5)]
        );
        p[4] = 0.5;
        p[3] = 0.;
        let mut pixels = vec![grayscale(0.), grayscale(1.), grayscale(0.5), grayscale(0.)];
        render(&mut pixels, 4, 1, &p, 1.).unwrap();
        assert_eq!(
            pixels,
            vec![
                grayscale(0.5),
                grayscale(0.25),
                grayscale(0.5),
                grayscale(0.25)
            ]
        );
    }
    #[test]
    fn directions_are_scan_orientations_not_arbitrary_rotations() {
        let source = vec![grayscale(0.), grayscale(1.), grayscale(0.5), grayscale(0.)];
        let mut p = params();
        p[3] = 1.;
        let mut right = source.clone();
        render(&mut right, 4, 1, &p, 1.).unwrap();
        p[0] = 2.;
        let mut down = source.clone();
        render(&mut down, 1, 4, &p, 1.).unwrap();
        assert_eq!(right, down);
        p[0] = 1.;
        let mut left = source.clone();
        render(&mut left, 4, 1, &p, 1.).unwrap();
        p[0] = 0.;
        let mut flipped = source;
        flipped.reverse();
        render(&mut flipped, 4, 1, &p, 1.).unwrap();
        flipped.reverse();
        assert_eq!(left, flipped);
        p[0] = 3.;
        let mut up = vec![grayscale(0.), grayscale(1.), grayscale(0.5), grayscale(0.)];
        render(&mut up, 1, 4, &p, 1.).unwrap();
        assert_eq!(left, up);
    }
    #[test]
    fn edge_modes_and_large_shifts_integrate_without_unbounded_iteration() {
        let source = vec![grayscale(0.), grayscale(1.), grayscale(0.5), grayscale(0.)];
        let mut p = params();
        p[4] = 0.5;
        let expected = [
            vec![0.5, 0.25, 0.5, 0.25],
            vec![0.5, 0.25, 0.25, 0.5],
            vec![0.5, 0.25, 0., 0.],
        ];
        for (edge, expected) in expected.iter().enumerate() {
            let mut out = source.clone();
            p[18] = edge as f64;
            render(&mut out, 4, 1, &p, 1.).unwrap();
            for (value, &gray) in out.iter().zip(expected) {
                near(value, &grayscale(gray));
            }
        }
        p[18] = 3.;
        let mut out = source.clone();
        render(&mut out, 4, 1, &p, 1.).unwrap();
        assert_eq!(out[2], [0.; 4]);
        p[18] = 0.;
        p[11] = 999_720.;
        p[12] = 0.;
        let mut out = source;
        render(&mut out, 4, 1, &p, 1.).unwrap();
        assert!(out.iter().flatten().all(|v| v.is_finite()));
    }
    #[test]
    fn intensity_zero_and_neutral_geometry_preserve_hdr_exactly_at_preview_scale() {
        let source = vec![[2., 1., 0.5, 0.5], [0.; 4], grayscale(0.25)];
        let mut p = params();
        let mut out = source.clone();
        render(&mut out, 3, 1, &p, 0.5).unwrap();
        assert_eq!(out, source);
        p[2] = 0.;
        p[3] = 100.;
        p[11] = 200.;
        p[17] = 80.;
        let mut out = source.clone();
        render(&mut out, 3, 1, &p, 0.5).unwrap();
        assert_eq!(out, source);
    }
    #[test]
    fn controls_change_original_geometry_and_channels_preserve_unselected_values() {
        let source = vec![
            [0., 0.1, 0.2, 0.5],
            [1., 0.3, 0.4, 1.],
            [0.4, 0.3, 0.2, 0.8],
            [0.; 4],
        ];
        let mut p = params();
        p[3] = 2.;
        p[1] = 2.;
        let mut out = source.clone();
        render(&mut out, 4, 1, &p, 1.).unwrap();
        for (a, b) in out.iter().zip(&source) {
            near(&[a[1], a[2], a[3], 0.], &[b[1], b[2], b[3], 0.]);
        }
        assert_ne!(out, source);
        p[1] = 0.;
        let mut baseline = source.clone();
        render(&mut baseline, 4, 1, &p, 1.).unwrap();
        for (index, value) in [
            (5, 1.),
            (6, 90.),
            (7, 75.),
            (8, 75.),
            (9, 1.),
            (9, 2.),
            (10, 0.1),
            (11, 90.),
        ] {
            let mut controls = p;
            controls[index] = value;
            let mut out = source.clone();
            render(&mut out, 4, 1, &controls, 1.).unwrap();
            assert_ne!(out, baseline, "control {index}");
        }
        p[11] = 90.;
        let mut a = source.clone();
        render(&mut a, 4, 1, &p, 1.).unwrap();
        p[12] = 0.;
        let mut b = source;
        render(&mut b, 4, 1, &p, 1.).unwrap();
        assert_ne!(a, b);
    }
    #[test]
    fn alpha_shading_feather_and_invalid_parameters_are_explicit() {
        let source = vec![grayscale(1.); 4];
        let mut p = params();
        p[13] = 3.;
        p[14] = 4.;
        p[17] = 100.;
        let mut out = source.clone();
        render(&mut out, 4, 1, &p, 1.).unwrap();
        near(&out[2], &[0.5; 4]);
        p[16] = 1.;
        let mut out = source.clone();
        render(&mut out, 4, 1, &p, 1.).unwrap();
        near(&out[2], &[0.5, 0.5, 0.5, 1.]);
        p = params();
        p[4] = 0.5;
        p[18] = 3.;
        p[19] = 100.;
        let mut out = source.clone();
        render(&mut out, 4, 1, &p, 1.).unwrap();
        assert!(out[0][3] > 0. && out[0][3] < 1. && out[2][3] == 0.);
        for (index, value) in [
            (0, 4.),
            (1, 0.5),
            (2, -1.),
            (3, f64::NAN),
            (4, 0.),
            (12, 2.),
            (18, 4.),
        ] {
            let mut controls = params();
            controls[index] = value;
            let mut out = source.clone();
            assert!(render(&mut out, 4, 1, &controls, 1.).is_err());
            assert_eq!(out, source);
        }
        let mut out = source.clone();
        assert!(render(&mut out, 4, 1, &params(), 0.).is_err());
        assert_eq!(out, source);
    }

    #[test]
    fn all_channels_curves_and_shading_modes_are_finite_and_effective() {
        let source = vec![
            [0.05, 0.1, 0.15, 0.5],
            [0.7, 0.5, 0.3, 1.],
            [0.1, 0.5, 0.05, 0.6],
            [0.1, 0.05, 0.2, 0.25],
        ];
        for channels in 0..8 {
            for curve in 0..6 {
                let mut p = params();
                p[1] = channels as f64;
                p[5] = curve as f64;
                p[3] = 1.7;
                let mut out = source.clone();
                render(&mut out, 4, 1, &p, 1.).unwrap();
                assert!(out.iter().flatten().all(|v| v.is_finite()));
                assert_ne!(out, source, "channels {channels}, curve {curve}");
                if channels >= 6 {
                    for (a, b) in out.iter().zip(&source) {
                        assert_eq!(a[3], b[3]);
                    }
                }
            }
        }
        for mode in 1..=5 {
            let mut p = params();
            p[13] = mode as f64;
            p[14] = 2.3;
            p[15] = if mode == 5 { 0. } else { 45. };
            p[17] = 75.;
            let mut out = source.clone();
            render(&mut out, 4, 1, &p, 1.).unwrap();
            assert!(out.iter().flatten().all(|v| v.is_finite()));
            assert_ne!(out, source);
        }
    }
}
