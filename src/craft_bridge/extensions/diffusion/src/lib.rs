//! Original bounded palette error diffusion for EffectCraft API v1.
//! Independent approximation; no source plugin code or assets. See ADR 014.

use std::cell::RefCell;

const MANIFEST: &str = include_str!("../manifest.json");
const FLAT_PARAMS: usize = 38;
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
    p.len() == FLAT_PARAMS
        && p.iter().all(|v| v.is_finite())
        && scale.is_finite()
        && scale > 0.0
        && scale <= 16.0
        && (-4.0..=4.0).contains(&p[0])
        && (-4.0..=4.0).contains(&p[1])
        && p[2..6].iter().all(|v| (0.0..=1.0).contains(v))
        && (0.0..=3.0).contains(&p[6])
        && p[6] == p[6].floor()
        && (0.0..=5.0).contains(&p[7])
        && p[7] == p[7].floor()
        && (0..6).all(|i| {
            p[8 + 5 * i..12 + 5 * i]
                .iter()
                .all(|v| (0.0..=1.0).contains(v))
                && (1.0..=4096.0).contains(&p[12 + 5 * i])
        })
}

fn quant(v: f64) -> f64 {
    (v.clamp(0.0, 1.0) * 255.0).round() / 255.0
}

fn render(
    px: &mut [[f32; 4]],
    width: usize,
    height: usize,
    p: &[f64],
    scale: f64,
) -> Result<(), ()> {
    if !valid(p, scale)
        || width == 0
        || height == 0
        || width > MAX_SIDE
        || height > MAX_SIDE
        || width.checked_mul(height) != Some(px.len())
        || px.len() > MAX_PIXELS
        || px.iter().any(|x| {
            x.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&x[3])
        })
    {
        return Err(());
    }
    let direction = p[6] as usize;
    let (length, lines) = if direction < 2 {
        (width, height)
    } else {
        (height, width)
    };
    let palette: [[f64; 4]; 6] =
        std::array::from_fn(|i| std::array::from_fn(|c| quant(p[8 + 5 * i + c])));
    let runs: [usize; 6] =
        std::array::from_fn(|i| (p[12 + 5 * i] * scale).round().max(1.0) as usize);
    let count = p[7] as usize + 1;
    let phase = [p[2], p[3], p[4]];
    let mut aside = vec![[0.0; 3]; length];
    let mut next = vec![[0.0; 3]; length];
    for line in 0..lines {
        let mut across = phase;
        let mut remaining: usize = 0;
        let mut chosen = 0;
        for pos in 0..length {
            let coordinate = if direction.is_multiple_of(2) {
                pos
            } else {
                length - 1 - pos
            };
            let index = if direction < 2 {
                line * width + coordinate
            } else {
                coordinate * width + line
            };
            let input = px[index];
            let alpha = input[3] as f64;
            if alpha <= 1e-12 {
                px[index] = [0.0; 4];
                remaining = remaining.saturating_sub(1);
                continue;
            }
            let desired: [f64; 3] = std::array::from_fn(|c| {
                (quant(input[c] as f64 / alpha) + across[c] + aside[pos][c]).clamp(-1024.0, 1024.0)
            });
            if remaining == 0 {
                let mut best = f64::INFINITY;
                for (i, color) in palette.iter().enumerate().take(count) {
                    let distance = (0..3).map(|c| (desired[c] - color[c]).powi(2)).sum::<f64>();
                    if distance < best {
                        best = distance;
                        chosen = i;
                    }
                }
                remaining = runs[chosen];
            }
            let color = palette[chosen];
            let output_alpha = alpha * color[3];
            px[index] = std::array::from_fn(|c| {
                if c == 3 {
                    output_alpha as f32
                } else {
                    (color[c] * output_alpha) as f32
                }
            });
            for c in 0..3 {
                let error = desired[c] - color[c];
                across[c] = (error * p[0]).clamp(-1024.0, 1024.0);
                next[pos][c] = (error * p[1]).clamp(-1024.0, 1024.0);
            }
            remaining -= 1;
        }
        std::mem::swap(&mut aside, &mut next);
        next.fill([0.0; 3]);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn params() -> [f64; FLAT_PARAMS] {
        let mut p = [0.0; FLAT_PARAMS];
        p[0] = 1.0;
        p[5] = 1.0;
        p[7] = 1.0;
        for i in 0..6 {
            p[11 + 5 * i] = 1.0;
            p[12 + 5 * i] = 1.0;
        }
        p[13..16].fill(1.0);
        p
    }
    fn gray(v: f32) -> [f32; 4] {
        [v, v, v, 1.0]
    }
    #[test]
    fn hand_calculated_diffusion_and_zero_error() {
        let mut p = params();
        let mut x = vec![gray(0.25); 4];
        render(&mut x, 4, 1, &p, 1.0).unwrap();
        assert_eq!(x, vec![gray(0.0), gray(1.0), gray(0.0), gray(0.0)]);
        p[0] = 0.0;
        let mut x = vec![gray(0.25); 4];
        render(&mut x, 4, 1, &p, 1.0).unwrap();
        assert_eq!(x, vec![gray(0.0); 4]);
    }
    #[test]
    fn widths_phase_and_aside_are_effective() {
        let mut p = params();
        p[17] = 2.0;
        let mut x = vec![gray(0.6); 4];
        render(&mut x, 4, 1, &p, 1.0).unwrap();
        assert_eq!(x, vec![gray(1.0), gray(1.0), gray(0.0), gray(0.0)]);
        p = params();
        p[0] = 0.0;
        p[1] = 1.0;
        let mut x = vec![gray(0.25); 2];
        render(&mut x, 1, 2, &p, 1.0).unwrap();
        assert_eq!(x, vec![gray(0.0), gray(1.0)]);
        p[1] = 0.0;
        p[2..5].fill(0.5);
        let mut x = vec![gray(0.25)];
        render(&mut x, 1, 1, &p, 1.0).unwrap();
        assert_eq!(x, vec![gray(1.0)]);
    }
    #[test]
    fn direction_transposition_and_reversal() {
        for direction in 0..4 {
            let mut p = params();
            p[6] = direction as f64;
            let mut x = vec![gray(0.25); 4];
            let (w, h) = if direction < 2 { (4, 1) } else { (1, 4) };
            render(&mut x, w, h, &p, 1.0).unwrap();
            let mut expected = vec![gray(0.0), gray(1.0), gray(0.0), gray(0.0)];
            if direction % 2 == 1 {
                expected.reverse();
            }
            assert_eq!(x, expected);
        }
    }
    #[test]
    fn premultiplied_alpha_palette_and_transparency() {
        let mut p = params();
        p[0] = 0.0;
        p[7] = 0.0;
        p[8] = 1.0;
        p[11] = 0.5;
        let mut x = vec![[0.25, 0.0, 0.0, 0.5], [0.0; 4]];
        render(&mut x, 2, 1, &p, 1.0).unwrap();
        let a = 128.0 / 255.0 * 0.5;
        assert!((x[0][0] - a).abs() < 1e-6);
        assert_eq!(x[0][0], x[0][3]);
        assert_eq!(x[1], [0.0; 4]);
    }
    #[test]
    fn all_palettes_preview_and_unstable_coefficients_are_bounded() {
        for count in 0..6 {
            let mut p = params();
            p[7] = count as f64;
            p[0] = -4.0;
            p[1] = 4.0;
            let mut x = vec![gray(0.25); 4096];
            render(&mut x, 64, 64, &p, 0.5).unwrap();
            assert!(
                x.iter()
                    .flatten()
                    .all(|v| v.is_finite() && (0.0..=1.0).contains(v))
            );
        }
    }
    #[test]
    fn invalid_parameters_and_input_preserve_pixels() {
        for (index, value) in [
            (0, 4.01),
            (1, f64::NAN),
            (6, 4.0),
            (7, 1.5),
            (8, -0.1),
            (12, 0.0),
        ] {
            let mut p = params();
            p[index] = value;
            let mut x = vec![gray(0.5)];
            let before = x.clone();
            assert!(render(&mut x, 1, 1, &p, 1.0).is_err());
            assert_eq!(x, before);
        }
        let p = params();
        let mut x = vec![[2.0, 0.0, 0.0, 2.0]];
        let before = x.clone();
        assert!(render(&mut x, 1, 1, &p, 1.0).is_err());
        assert_eq!(x, before);
    }
}
