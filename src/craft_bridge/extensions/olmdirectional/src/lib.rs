//! Original anisotropic alpha-max rays and component-based modulation, not OLM code.
use std::cell::RefCell;
const MANIFEST: &str = include_str!("../manifest.json");
const FLAT: usize = 17;
const MAX_PIXELS: usize = 2_097_152;
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
        && (1. / 65536. ..=16.).contains(&scale)
        && p.iter().enumerate().all(|(i, &v)| {
            v.is_finite()
                && match i {
                    0 | 1 => v.fract() == 0. && (0. ..=u32::MAX as f64).contains(&v),
                    2 | 13 => v.fract() == 0. && (0. ..=2.).contains(&v),
                    3 | 15 => v.abs() <= 360000.,
                    4 => (0. ..=64.).contains(&v),
                    5 | 7 | 8 | 10 | 11 | 12 => (0. ..=100.).contains(&v),
                    6 | 9 => (0. ..=4000.).contains(&v),
                    14 => v.abs() <= 1e9,
                    16 => (1. ..=100.).contains(&v),
                    _ => false,
                }
        })
}
include!("helpers.rs");
fn world(img: &Image, i: usize) -> [f64; 2] {
    [
        ((i % img.w) as f64 + 0.5 - img.geo.offset[0]) / img.geo.scale,
        ((i / img.w) as f64 + 0.5 - img.geo.offset[1]) / img.geo.scale,
    ]
}
fn nearest(img: &Image, point: [f64; 2]) -> Option<usize> {
    let x = (point[0] * img.geo.scale + img.geo.offset[0] - 0.5).round();
    let y = (point[1] * img.geo.scale + img.geo.offset[1] - 0.5).round();
    if x < 0. || y < 0. || x >= img.w as f64 || y >= img.h as f64 {
        None
    } else {
        Some(y as usize * img.w + x as usize)
    }
}
struct Group {
    count: usize,
    lo: f64,
    hi: f64,
}
struct Components {
    labels: Vec<usize>,
    groups: Vec<Group>,
    min: usize,
    max: usize,
}
fn components(img: &Image, perp: [f64; 2]) -> Result<Components, ()> {
    let n = img.pixels.len();
    let mut labels = zeros::<usize>(n)?;
    let mut groups = Vec::new();
    let mut queue = Vec::new();
    queue.try_reserve_exact(n).map_err(|_| ())?;
    let mut min = usize::MAX;
    let mut max = 0;
    for start in 0..n {
        if img.pixels[start][3] == 0. || labels[start] != 0 {
            continue;
        }
        groups.try_reserve(1).map_err(|_| ())?;
        let id = groups.len() + 1;
        queue.clear();
        queue.push(start);
        labels[start] = id;
        let mut group = Group {
            count: 0,
            lo: f64::INFINITY,
            hi: f64::NEG_INFINITY,
        };
        while let Some(i) = queue.pop() {
            group.count += 1;
            let pos = world(img, i);
            let cross = pos[0] * perp[0] + pos[1] * perp[1];
            group.lo = group.lo.min(cross);
            group.hi = group.hi.max(cross);
            let x = i % img.w;
            let y = i / img.w;
            for dy in -1isize..=1 {
                for dx in -1isize..=1 {
                    let xx = x as isize + dx;
                    let yy = y as isize + dy;
                    if xx < 0 || yy < 0 || xx >= img.w as isize || yy >= img.h as isize {
                        continue;
                    }
                    let j = yy as usize * img.w + xx as usize;
                    if labels[j] == 0 && img.pixels[j][3] > 0. {
                        labels[j] = id;
                        queue.push(j);
                    }
                }
            }
        }
        min = min.min(group.count);
        max = max.max(group.count);
        groups.push(group);
    }
    Ok(Components {
        labels,
        groups,
        min,
        max,
    })
}
fn hash(x: i64, seed: f64) -> f64 {
    let mut bits = (x as u64) ^ seed.to_bits().rotate_left(17);
    bits ^= bits >> 30;
    bits = bits.wrapping_mul(0xbf58476d1ce4e5b9);
    bits ^= bits >> 27;
    bits = bits.wrapping_mul(0x94d049bb133111eb);
    bits ^= bits >> 31;
    (bits >> 11) as f64 / (1u64 << 53) as f64
}
fn noise_at(noise: Option<&Image>, point: [f64; 2], perp: [f64; 2], p: &[f64]) -> f64 {
    if p[13] == 2. {
        let c = sample(noise, point);
        return (c[0] as f64 * 0.25 + c[1] as f64 * 0.5 + c[2] as f64 * 0.25).clamp(0., 1.);
    }
    let q = (point[0] * perp[0] + point[1] * perp[1]) / p[16] + p[15] / 360.;
    let cell = q.floor() as i64;
    let a = hash(cell, p[14]);
    if p[13] == 1. {
        return a;
    }
    let f = q - cell as f64;
    let t = f * f * (3. - 2. * f);
    a * (1. - t) + hash(cell + 1, p[14]) * t
}
fn size_factor(group: &Group, all: &Components, variation: f64) -> f64 {
    let normalized = if all.max == all.min {
        0.
    } else {
        ((group.count as f64).sqrt() - (all.min as f64).sqrt())
            / ((all.max as f64).sqrt() - (all.min as f64).sqrt())
    };
    1. - variation / 100. + variation / 100. * normalized
}
fn render(
    main: &Image,
    noise: Option<&Image>,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<Vec<Pixel>, ()> {
    if !valid(p, time, scale)
        || main.w == 0
        || main.h == 0
        || main.w.checked_mul(main.h) != Some(main.pixels.len())
        || main.pixels.len() > MAX_PIXELS
        || main.geo.scale != scale
        || main
            .geo
            .offset
            .iter()
            .any(|v| !v.is_finite() || v.abs() > 1e9)
        || main.pixels.iter().any(|c| {
            c.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0. ..=1.).contains(&c[3])
        })
    {
        return Err(());
    }
    if p[13] == 2.
        && noise.is_some_and(|n| {
            n.w != main.w
                || n.h != main.h
                || n.geo.scale != scale
                || n.geo.offset != main.geo.offset
                || n.w.checked_mul(n.h) != Some(n.pixels.len())
                || n.pixels.iter().any(|c| {
                    c.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0. ..=1.).contains(&c[3])
                })
        })
    {
        return Err(());
    }
    let angle = p[3].to_radians();
    let dir = [angle.cos(), angle.sin()];
    let perp = [-dir[1], dir[0]];
    let groups = if p[5] > 0. || p[8] > 0. || p[11] > 0. {
        Some(components(main, perp)?)
    } else {
        None
    };
    let mut out = zeros(main.pixels.len())?;
    for (i, dst) in out.iter_mut().enumerate() {
        let point = world(main, i);
        let mut best = if main.pixels[i][3] > 0. {
            main.pixels[i]
        } else {
            [0.; 4]
        };
        if best[3] < 1. {
            for (sign, base, fade, tail) in [(1., p[6], p[7], p[8]), (-1., p[9], p[10], p[11])] {
                if base == 0. {
                    continue;
                }
                let steps = (base * scale).ceil().clamp(1., 64.) as usize;
                for step in 1..=steps {
                    let distance = base * step as f64 / steps as f64;
                    let source = [
                        point[0] - sign * dir[0] * distance,
                        point[1] - sign * dir[1] * distance,
                    ];
                    let Some(index) = nearest(main, source) else {
                        continue;
                    };
                    if main.pixels[index][3] == 0. {
                        continue;
                    }
                    let group = if let Some(all) = groups.as_ref() {
                        let id = all.labels[index];
                        if id == 0 {
                            continue;
                        }
                        Some((&all.groups[id - 1], all))
                    } else {
                        None
                    };
                    let factor = group.map_or(1., |(g, all)| size_factor(g, all, p[5]));
                    let length = base
                        * factor
                        * (1. - p[12] / 100. + p[12] / 100. * noise_at(noise, source, perp, p));
                    if length <= 0. || distance > length + 1e-9 {
                        continue;
                    }
                    let q = distance / length;
                    if let Some((g, _)) = group {
                        let cross = source[0] * perp[0] + source[1] * perp[1];
                        let half = ((g.hi - g.lo) / 2. + 0.5 / scale) * (1. - tail / 100. * q);
                        if (cross - (g.lo + g.hi) / 2.).abs() > half + 1e-9 {
                            continue;
                        }
                    }
                    let mut candidate = sample(Some(main), source);
                    let weight = 1. - fade / 100. * q;
                    for c in &mut candidate {
                        *c = (*c as f64 * weight) as f32;
                    }
                    if candidate[3] > best[3] {
                        best = candidate;
                    }
                }
            }
        }
        if best[3] == 0. {
            best = [0.; 4];
        }
        for c in &mut best[..3] {
            *c = (*c as f64 * p[4]) as f32;
        }
        if best.iter().any(|v| !v.is_finite()) {
            return Err(());
        }
        *dst = best;
    }
    Ok(out)
}
include!("abi.rs");
#[cfg(test)]
mod tests;
