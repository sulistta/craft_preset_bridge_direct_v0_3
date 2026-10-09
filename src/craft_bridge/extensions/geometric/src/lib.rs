//! Original proximity-matching painter; no proprietary algorithm or inferred units.
use std::cell::RefCell;
use std::f64::consts::TAU;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 21;
const MAX_PIXELS: usize = 2_097_152;
type Pixel = [f32; 4];
type Point = [f64; 2];
#[derive(Clone, Copy, PartialEq)]
struct Geometry {
    offset: Point,
    scale: f64,
    size: Point,
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
        && (1. / 65536. ..=16.).contains(&scale)
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 | 8 => v == 0. || v == 1.,
                    1 => v.fract() == 0. && (0. ..=1024.).contains(&v),
                    2 => v.fract() == 0. && (0. ..=5.).contains(&v),
                    3 => (0. ..=10000.).contains(&v),
                    4 => (0. ..=16.).contains(&v),
                    5 | 6 => (0. ..=2048.).contains(&v),
                    7 => (0. ..=512.).contains(&v),
                    10 => v.abs() <= 1e6,
                    11 | 12 => (0. ..=1e6).contains(&v),
                    14 => v.fract() == 0. && (0. ..=4.).contains(&v),
                    16 | 17 => (0. ..=255.).contains(&v),
                    18 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    20 => v.abs() <= 1e9,
                    _ => (0. ..=100.).contains(&v),
                }
        })
}
fn random(seed: f64, index: usize, step: usize, salt: u64) -> f64 {
    let mut n = seed.to_bits()
        ^ (index as u64).wrapping_mul(0x9e3779b97f4a7c15)
        ^ (step as u64).wrapping_mul(0xbf58476d1ce4e5b9)
        ^ salt;
    n ^= n >> 30;
    n = n.wrapping_mul(0xbf58476d1ce4e5b9);
    n ^= n >> 27;
    n = n.wrapping_mul(0x94d049bb133111eb);
    n ^= n >> 31;
    (n >> 11) as f64 / ((1u64 << 53) - 1) as f64
}
fn sample(img: &Image, at: Point) -> Pixel {
    let x = (at[0] * img.geo.scale + img.geo.offset[0] - 0.5).round() as isize;
    let y = (at[1] * img.geo.scale + img.geo.offset[1] - 0.5).round() as isize;
    if x < 0 || y < 0 || x >= img.w as isize || y >= img.h as isize {
        [0.; 4]
    } else {
        img.pixels[y as usize * img.w + x as usize]
    }
}
fn length(a: Point, b: Point) -> f64 {
    ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2)).sqrt()
}
fn segment(q: Point, a: Point, b: Point) -> f64 {
    let d = [b[0] - a[0], b[1] - a[1]];
    let norm = d[0] * d[0] + d[1] * d[1];
    let t = if norm == 0. {
        0.
    } else {
        ((q[0] - a[0]) * d[0] + (q[1] - a[1]) * d[1]) / norm
    }
    .clamp(0., 1.);
    length(q, [a[0] + t * d[0], a[1] + t * d[1]])
}
fn blend(dst: &mut Pixel, src: Pixel, coverage: f64) {
    let a = (src[3] as f64 * coverage).clamp(0., 1.);
    let b = dst[3] as f64 * (1. - a);
    let alpha = a + b;
    for k in 0..3 {
        dst[k] = if alpha == 0. {
            0.
        } else {
            ((src[k] as f64 * a + dst[k] as f64 * b) / alpha) as f32
        };
    }
    dst[3] = alpha as f32;
}
struct Budget {
    visits: usize,
    probes: usize,
}
impl Budget {
    fn visit(&mut self) -> Result<(), ()> {
        self.visits += 1;
        if self.visits > 8_000_000 {
            Err(())
        } else {
            Ok(())
        }
    }
    fn probe(&mut self) -> Result<(), ()> {
        self.probes += 1;
        if self.probes > 1_000_000 {
            Err(())
        } else {
            Ok(())
        }
    }
}
#[allow(clippy::too_many_arguments)]
fn endpoint(
    img: &Image,
    start: Point,
    c: Pixel,
    angle: f64,
    size: f64,
    growth: f64,
    range: f64,
    accuracy: f64,
    budget: &mut Budget,
) -> Result<Option<(Point, f64)>, ()> {
    let mut best = None;
    let mut best_score = f64::INFINITY;
    for dir in 0..16 {
        let a = angle + (dir as f64 / 15. - 0.5) * range;
        let (sin, cos) = a.sin_cos();
        for grow in 0..3 {
            let dist = size + growth * grow as f64 / 2.;
            if dist <= 0. {
                continue;
            }
            let end = [start[0] + dist * cos, start[1] + dist * sin];
            let mut score = 0.;
            for f in [0.25, 0.5, 0.75, 1.] {
                budget.probe()?;
                let at = [
                    start[0] + (end[0] - start[0]) * f,
                    start[1] + (end[1] - start[1]) * f,
                ];
                let v = sample(img, at);
                score += if v[3] <= 0. {
                    1000.
                } else {
                    (0..3)
                        .map(|k| (v[k] as f64 - c[k] as f64).abs())
                        .sum::<f64>()
                        / 3.
                };
            }
            score /= 4.;
            if score < best_score {
                best_score = score;
                best = Some((end, a));
            }
        }
    }
    // Original RGB distance calibration, not Satori matching accuracy.
    Ok(if best_score <= (1. - accuracy / 100.) + 1e-6 {
        best
    } else {
        None
    })
}
fn polygon(q: Point, v: &[Point], fill: bool, width: f64) -> bool {
    let mut inside = false;
    let mut edge = f64::INFINITY;
    for i in 0..v.len() {
        let a = v[i];
        let b = v[(i + 1) % v.len()];
        edge = edge.min(segment(q, a, b));
        if (a[1] > q[1]) != (b[1] > q[1])
            && q[0] < (b[0] - a[0]) * (q[1] - a[1]) / (b[1] - a[1]) + a[0]
        {
            inside = !inside;
        }
    }
    if fill {
        inside || edge <= width * 0.5
    } else {
        edge <= width * 0.5
    }
}
#[allow(clippy::too_many_arguments)]
fn draw(
    out: &mut [Pixel],
    img: &Image,
    start: Point,
    end: Point,
    angle: f64,
    shape: usize,
    fill: bool,
    width: f64,
    color: Pixel,
    opacity: f64,
    budget: &mut Budget,
) -> Result<(), ()> {
    let radius = length(start, end);
    let (sin, cos) = angle.sin_cos();
    let center = [(start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5];
    let curve = [
        center[0] - sin * radius * 0.25,
        center[1] + cos * radius * 0.25,
    ];
    let rotate = |x: f64, y: f64| [center[0] + x * cos - y * sin, center[1] + x * sin + y * cos];
    let vertices: Vec<Point> = match shape {
        2 => (0..3)
            .map(|i| {
                let a = i as f64 * TAU / 3.;
                rotate(a.cos() * radius * 0.5, a.sin() * radius * 0.5)
            })
            .collect(),
        3 | 5 => {
            let ry = radius * if shape == 3 { 0.5 } else { 0.2 };
            vec![
                rotate(-radius * 0.5, -ry),
                rotate(radius * 0.5, -ry),
                rotate(radius * 0.5, ry),
                rotate(-radius * 0.5, ry),
            ]
        }
        _ => vec![],
    };
    let extent = radius + width + 1. / img.geo.scale;
    let low = [
        ((center[0] - extent) * img.geo.scale + img.geo.offset[0])
            .floor()
            .max(0.) as usize,
        ((center[1] - extent) * img.geo.scale + img.geo.offset[1])
            .floor()
            .max(0.) as usize,
    ];
    let high = [
        ((center[0] + extent) * img.geo.scale + img.geo.offset[0])
            .ceil()
            .max(0.)
            .min(img.w as f64) as usize,
        ((center[1] + extent) * img.geo.scale + img.geo.offset[1])
            .ceil()
            .max(0.)
            .min(img.h as f64) as usize,
    ];
    let mut curve_points = [[0.; 2]; 13];
    for (i, at) in curve_points.iter_mut().enumerate() {
        let t = i as f64 / 12.;
        *at = std::array::from_fn(|k| {
            (1. - t).powi(2) * start[k] + 2. * t * (1. - t) * curve[k] + t * t * end[k]
        });
    }
    for y in low[1]..high[1] {
        for x in low[0]..high[0] {
            budget.visit()?;
            let q = [
                (x as f64 + 0.5 - img.geo.offset[0]) / img.geo.scale,
                (y as f64 + 0.5 - img.geo.offset[1]) / img.geo.scale,
            ];
            let hit = match shape {
                0 => segment(q, start, end) <= width * 0.5,
                1 => curve_points
                    .windows(2)
                    .any(|v| segment(q, v[0], v[1]) <= width * 0.5),
                2 | 3 | 5 => polygon(q, &vertices, fill, width),
                4 => {
                    let d = length(q, center);
                    if fill {
                        d <= radius * 0.5 + width * 0.5
                    } else {
                        (d - radius * 0.5).abs() <= width * 0.5
                    }
                }
                _ => false,
            };
            if hit {
                blend(&mut out[y * img.w + x], color, opacity);
            }
        }
    }
    Ok(())
}
fn render(img: &Image, p: &[f64], time: f64, scale: f64, step: f64) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || !step.is_finite()
        || step <= 0.
        || img.w == 0
        || img.h == 0
        || img.w.checked_mul(img.h) != Some(img.pixels.len())
        || img.pixels.len() > MAX_PIXELS
    {
        return Err(());
    }
    let mut out = zeros(img.pixels.len())?;
    if p[0] == 1. {
        out.copy_from_slice(&img.pixels);
    }
    if p[3] < 1. || p[4] < 1. || p[5] == 0. || p[9] == 0. || p[16] > p[17] {
        return Ok(out);
    }
    let count = p[3].floor() as usize;
    let recursion = p[4].floor() as usize;
    let cols = ((count as f64 * img.geo.size[0] / img.geo.size[1])
        .sqrt()
        .ceil() as usize)
        .max(1);
    let rows = count.div_ceil(cols);
    let clock = if p[18] == 0. {
        (time / step).floor() as i64 as u64
    } else {
        0
    };
    let mut budget = Budget {
        visits: 0,
        probes: 0,
    };
    for i in 0..count {
        let random = |salt| random(p[20], i, 0, salt ^ clock);
        let mut start = if p[18] == 2. {
            [
                (i % cols) as f64 / cols as f64
                    + 0.5 / cols as f64
                    + (random(1) - 0.5) * p[19] / 100. / cols as f64,
                (i / cols) as f64 / rows as f64
                    + 0.5 / rows as f64
                    + (random(2) - 0.5) * p[19] / 100. / rows as f64,
            ]
        } else {
            [random(1), random(2)]
        };
        start[0] *= img.geo.size[0];
        start[1] *= img.geo.size[1];
        let color = sample(img, start);
        let luma = (color[0] as f64 * 0.25 + color[1] as f64 * 0.5 + color[2] as f64 * 0.25) * 255.;
        if color[3] <= 0. || luma < p[16] || luma > p[17] {
            continue;
        }
        let mut angle = (p[10] + (random(3) - 0.5) * p[11]) * TAU / 360.;
        for depth in 0..recursion {
            let Some((end, direction)) = endpoint(
                img,
                start,
                color,
                angle,
                p[5],
                p[6],
                p[12] * TAU / 360.,
                p[13],
                &mut budget,
            )?
            else {
                break;
            };
            let factor = match p[14] as usize {
                1 => 1. - ((length(start, end) - p[5]) / p[6].max(1e-9)).clamp(0., 1.),
                2 => ((length(start, end) - p[5]) / p[6].max(1e-9)).clamp(0., 1.),
                3 => 1. - depth as f64 / recursion.max(1) as f64,
                4 => depth as f64 / recursion.max(1) as f64,
                _ => 1.,
            };
            let fade = 1. - p[15] / 100. * (1. - factor);
            draw(
                &mut out,
                img,
                start,
                end,
                direction,
                p[2] as usize,
                p[8] == 1.,
                p[7],
                color,
                p[9] / 100. * fade,
                &mut budget,
            )?;
            start = end;
            angle = direction;
        }
    }
    if out.iter().flatten().all(|v| v.is_finite()) {
        Ok(out)
    } else {
        Err(())
    }
}
include!("abi.rs");
#[cfg(test)]
mod tests;
