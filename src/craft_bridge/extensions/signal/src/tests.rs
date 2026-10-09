use super::*;
fn neutral() -> [f64; FLAT] {
    let mut p = [0.; FLAT];
    p[1] = 100.;
    p[2] = 1.;
    p[3] = 100.;
    p[18] = 1.;
    p[21] = 1.;
    p[30] = 1.;
    p
}
fn image(w: usize, h: usize) -> Image {
    Image {
        w,
        h,
        geo: Geometry {
            offset: [0.; 2],
            scale: 1.,
            size: [w as f64, h as f64],
        },
        pixels: (0..w * h)
            .map(|i| {
                [
                    ((i * 13) % 37) as f32 / 37.,
                    ((i * 17) % 43) as f32 / 43.,
                    ((i * 19) % 53) as f32 / 53.,
                    (i % 7) as f32 / 6.,
                ]
            })
            .collect(),
    }
}
#[test]
fn own_opponent_transform_is_exactly_invertible_in_hdr() {
    for c in [
        [1., 0., 0., 1.],
        [-2., 3., 0.125, 0.5],
        [0.4, 0.4, 0.4, 0.1],
    ] {
        let out = decode(encode(c), c[3]);
        for k in 0..4 {
            assert!((out[k] - c[k]).abs() < 1e-6);
        }
    }
}
#[test]
fn neutral_chain_and_strength_zero_are_identity() {
    let img = image(13, 9);
    let p = neutral();
    let out = render(&img, &p, 0.17, 1.).unwrap();
    for (a, b) in out.iter().zip(&img.pixels) {
        for k in 0..4 {
            assert!((a[k] - b[k]).abs() < 1e-6);
        }
    }
    let mut noisy = p;
    noisy[1] = 0.;
    noisy[4] = 100.;
    noisy[5] = 100.;
    noisy[22] = 100.;
    assert_eq!(render(&img, &noisy, 0., 1.).unwrap(), img.pixels);
}
#[test]
fn gray_amplification_and_strength_have_independent_math() {
    let mut img = image(7, 5);
    img.pixels = vec![[0.25, 0.25, 0.25, 0.4]; 35];
    let mut p = neutral();
    p[2] = 3.;
    p[1] = 50.;
    assert!(
        render(&img, &p, 0., 1.)
            .unwrap()
            .iter()
            .all(|v| *v == [0.5, 0.5, 0.5, 0.4])
    );
    p[30] = 0.; // Composite also recovers DC without filtering.
    assert!(
        render(&img, &p, 0., 1.)
            .unwrap()
            .iter()
            .all(|v| *v == [0.5, 0.5, 0.5, 0.4])
    );
}
#[test]
fn all_processing_controls_have_active_contexts() {
    let img = image(31, 17);
    let mut p = neutral();
    p[0] = 1.25;
    p[4] = 7.;
    p[5] = 5.;
    p[6] = 15.;
    p[7] = 0.24;
    p[8] = 2.;
    p[10] = 1.;
    p[11] = 1.;
    p[12] = 0.62;
    p[13] = 2.;
    p[14] = 0.62;
    p[15] = 20.;
    p[16] = 1.;
    p[17] = 0.1;
    p[18] = 0.95;
    p[19] = 1.;
    p[20] = 45.;
    p[21] = 2.;
    p[22] = 4.;
    p[23] = 2.;
    p[24] = 12.;
    p[25] = 15.;
    p[26] = 1.;
    p[3] = 70.;
    p[27] = 1.;
    p[28] = 12.;
    p[29] = 17.;
    p[31] = 1.;
    p[32] = 1.;
    p[33] = 15.;
    let baseline = render(&img, &p, 0.37, 1.).unwrap();
    for (index, value) in [
        (0, 1.5),
        (1, 40.),
        (2, 2.),
        (3, 100.),
        (4, 0.),
        (5, 0.),
        (6, 0.),
        (7, 0.),
        (8, 0.),
        (9, 3.),
        (10, 2.),
        (11, 0.),
        (12, 1.2),
        (13, 70.),
        (14, 0.1),
        (15, 0.),
        (16, 0.),
        (17, 0.5),
        (18, 0.6),
        (19, 0.),
        (20, 0.),
        (21, 4.),
        (22, 0.),
        (23, 0.),
        (24, 0.),
        (25, 0.),
        (26, 0.),
        (27, 2.),
        (28, 0.),
        (29, 0.),
        (30, 0.),
        (31, 0.),
        (32, 0.),
        (33, 0.),
    ] {
        let mut changed = p;
        changed[index] = value;
        assert_ne!(
            render(&img, &changed, 0.37, 1.).unwrap(),
            baseline,
            "control {index}"
        );
    }
}
#[test]
fn temporal_randomness_is_repeatable_and_fractional_seed_is_preserved() {
    let img = image(11, 7);
    let mut p = neutral();
    p[0] = 1.25;
    p[4] = 20.;
    let a = render(&img, &p, 0., 1.).unwrap();
    let b = render(&img, &p, 1., 1.).unwrap();
    assert_ne!(a, b);
    assert_eq!(a, render(&img, &p, 0., 1.).unwrap());
    p[0] = 1.5;
    assert_ne!(a, render(&img, &p, 0., 1.).unwrap());
}
#[test]
fn tape_probability_interval_fade_and_gamma_are_bounded() {
    let mut p = neutral();
    p[16] = 1.;
    p[17] = 0.2;
    p[18] = 0.8;
    p[19] = 1.;
    p[20] = 0.;
    assert_eq!(tape_amount(&p, 0.5, 0.), 1.);
    assert_eq!(tape_amount(&p, 0.1, 0.), 0.);
    p[20] = 40.;
    assert!(tape_amount(&p, 0.4, 0.) > 0. && tape_amount(&p, 0.4, 0.) < 1.);
    let a = tape_amount(&p, 0.4, 0.);
    p[21] = 3.;
    assert!((tape_amount(&p, 0.4, 0.) - a.powi(3)).abs() < 1e-12);
    p[19] = 0.;
    assert_eq!(tape_amount(&p, 0.5, 0.), 0.);
    p[19] = 1.;
    p[17] = 0.8;
    p[18] = 0.2;
    assert_eq!(tape_amount(&p, 0.5, 0.), 0.);
}
#[test]
fn periodic_geometry_roll_and_alpha_use_explicit_rules() {
    let img = image(8, 4);
    let mut p = neutral();
    p[25] = 100.;
    let a = render(&img, &p, 0.5, 1.).unwrap();
    for (i, pixel) in a.iter().enumerate() {
        for (k, value) in pixel.iter().enumerate().take(3) {
            assert!((*value - img.pixels[(i + 16) % 32][k]).abs() < 1e-6);
        }
        assert_eq!(pixel[3], img.pixels[i][3]);
    }
    assert_eq!(periodic_sample(&img, -1., -1.), img.pixels[31]);
}
#[test]
fn all_vhs_and_receiver_options_are_distinct() {
    let img = image(17, 9);
    let mut p = neutral();
    p[26] = 1.;
    p[3] = 50.;
    let mut frames = Vec::new();
    for mode in 0..3 {
        p[10] = mode as f64;
        frames.push(render(&img, &p, 0., 1.).unwrap());
    }
    assert!(frames.windows(2).all(|v| v[0] != v[1]));
    p = neutral();
    frames.clear();
    for mode in 0..3 {
        p[27] = mode as f64;
        frames.push(render(&img, &p, 0., 1.).unwrap());
    }
    assert!(frames.windows(2).all(|v| v[0] != v[1]));
}
#[test]
fn reduced_scale_uses_source_geometry_for_modulation() {
    let mut full = image(8, 4);
    full.pixels = vec![[0.25, 0.25, 0.25, 1.]; 32];
    let mut half = image(4, 2);
    half.pixels = vec![[0.25, 0.25, 0.25, 1.]; 8];
    half.geo.scale = 0.5;
    half.geo.size = [8., 4.];
    let mut p = neutral();
    p[11] = 1.;
    p[12] = 0.125;
    p[14] = 0.5;
    let a = render(&full, &p, 0., 1.).unwrap();
    let b = render(&half, &p, 0., 0.5).unwrap();
    for y in 0..2 {
        let expected = 0.25 * (1. + 0.5 * (TAU * ((y as f64 + 0.5) / 2.)).sin());
        assert!((b[y * 4][0] as f64 - expected).abs() < 1e-6);
    }
    assert_ne!(a[0], b[0]); // Samples have different centers, not alleged visual equality.
}
#[test]
fn invalid_values_and_host_descriptor_fields_are_rejected() {
    let img = image(4, 2);
    let p = neutral();
    for (i, v) in [
        (0, -1.),
        (1, 101.),
        (7, 2.),
        (10, 0.5),
        (27, 3.),
        (11, 2.),
        (21, -1.),
        (33, f64::NAN),
    ] {
        let mut bad = p;
        bad[i] = v;
        assert!(render(&img, &bad, 0., 1.).is_err());
    }
    assert!(render(&img, &p, f64::INFINITY, 1.).is_err());
    let mut data = vec![0u8; FLAT * 8 + 80 + 16];
    let d = FLAT * 8;
    data[d..d + 4].copy_from_slice(&u32::MAX.to_le_bytes());
    data[d + 12..d + 16].copy_from_slice(&1u32.to_le_bytes());
    data[d + 16..d + 20].copy_from_slice(&((d + 80) as u32).to_le_bytes());
    for off in [20, 24] {
        data[d + off..d + off + 4].copy_from_slice(&1u32.to_le_bytes());
    }
    for off in [48, 56, 64] {
        data[d + off..d + off + 8].copy_from_slice(&1f64.to_le_bytes());
    }
    assert!(super::image(&data, 0, 0, d + 80, u32::MAX, [0, 0], true).is_ok());
    for off in [28, 72, 76] {
        data[d + off] = 1;
        assert!(super::image(&data, 0, 0, d + 80, u32::MAX, [0, 0], true).is_err());
        data[d + off] = 0;
    }
}
