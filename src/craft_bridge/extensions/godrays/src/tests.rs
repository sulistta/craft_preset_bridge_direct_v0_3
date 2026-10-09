use super::*;
fn params() -> [f64; FLAT] {
    [
        1.,
        1. / 16.,
        1. / 8.,
        0.,
        0.,
        0.,
        10000.,
        90.,
        0.,
        0.,
        0.,
        0.,
        0.,
        4.,
        2.,
        0.,
        1.,
        0.,
        100.,
        0.,
        1.,
        1.,
        0.,
        0.,
        0.,
        0.,
    ]
}
fn img() -> Image {
    let mut pixels = vec![[0.; 4]; 32];
    pixels[20] = [1., 0., 0., 1.];
    Image {
        pixels,
        w: 8,
        h: 4,
        geo: Geometry {
            offset: [0.; 2],
            scale: 1.,
            size: [8., 4.],
        },
    }
}
#[test]
fn two_tap_zoom_directions_have_analytic_impulse_response() {
    let src = img();
    let mut p = params();
    let out = render(&src, &p, 0., 1.).unwrap();
    for (i, px) in out.iter().enumerate() {
        assert_eq!(
            *px,
            if i == 20 {
                [1., 0., 0., 1.]
            } else {
                [0.5, 0., 0., 0.5]
            }
        );
    }
    p[10] = 1.;
    assert_eq!(render(&src, &p, 0., 1.).unwrap(), src.pixels);
    p[10] = 2.;
    for (i, px) in render(&src, &p, 0., 1.).unwrap().iter().enumerate() {
        assert_eq!(
            *px,
            if i == 20 {
                [1., 0., 0., 1.]
            } else {
                [0.25, 0., 0., 0.25]
            }
        );
    }
}
#[test]
fn spin_uses_degree_rotation_around_raw_position_model() {
    let mut src = img();
    src.pixels[20] = [0.; 4];
    src.pixels[21] = [1., 0., 0., 1.];
    let mut p = params();
    p[0] = 0.;
    let out = render(&src, &p, 0., 1.).unwrap();
    assert_eq!(out[28], [0.5, 0., 0., 0.5]);
    assert_eq!(out[21], [0.5, 0., 0., 0.5]);
    p[7] = 0.;
    assert_eq!(render(&src, &p, 0., 1.).unwrap(), src.pixels);
}
#[test]
fn threshold_operates_on_straight_color_and_never_hidden_rgb() {
    let mut p = params();
    p[4] = 50.;
    assert_eq!(gate([1., 0., 0., 1.], &p), [0.; 4]);
    p[3] = 1.;
    assert_eq!(gate([1., 0., 0., 1.], &p), [1., 0., 0., 1.]);
    assert_eq!(gate([0.5, 0.5, 0.5, 1.], &p), [0.; 4]);
    p[3] = 0.;
    p[4] = 25.;
    p[5] = 50.;
    assert_eq!(
        gate([0.25, 0.25, 0.25, 0.5], &p),
        [0.125, 0.125, 0.125, 0.25]
    );
    assert_eq!(gate([1e6, -1e6, 1e6, 0.], &p), [0.; 4]);
}
#[test]
fn decay_is_normalized_and_exposure_only_scales_rgb_before_unmult() {
    let src = img();
    let mut p = params();
    p[9] = 2.;
    p[8] = 1.;
    let expected = 2. * (-2f64).exp() / (1. + (-2f64).exp());
    let out = render(&src, &p, 0., 1.).unwrap();
    assert!((out[0][0] as f64 - expected).abs() < 1e-6);
    assert!((out[0][3] as f64 - expected).abs() < 1e-6);
    assert_eq!(out[20], [2., 0., 0., 1.]);
    p[20] = 0.;
    assert!((render(&src, &p, 0., 1.).unwrap()[0][3] as f64 - expected / 2.).abs() < 1e-6);
}
#[test]
fn repeat_edges_and_bilinear_transparent_border_are_distinct() {
    let mut src = img();
    src.pixels.fill([1., 0., 0., 1.]);
    assert_eq!(sample(&src, [0., 0.5], true), [1., 0., 0., 1.]);
    assert_eq!(sample(&src, [0., 0.5], false), [0.5, 0., 0., 0.5]);
    assert_eq!(sample(&src, [-2., 0.5], false), [0.; 4]);
}
#[test]
fn alpha_views_input_opacity_and_blends_are_independent() {
    let mut src = img();
    src.pixels.fill([0.2, 0.2, 0.2, 1.]);
    let mut p = params();
    let ray = render(&src, &p, 0., 1.).unwrap();
    assert_eq!(ray[0], [0.2; 4]);
    p[20] = 0.;
    assert_eq!(render(&src, &p, 0., 1.).unwrap()[0], [0.2, 0.2, 0.2, 1.]);
    p[20] = 1.;
    p[21] = 0.;
    p[18] = 50.;
    assert_eq!(render(&src, &p, 0., 1.).unwrap()[0], [0.1, 0.1, 0.1, 0.5]);
    p[21] = 2.;
    let screen = render(&src, &p, 0., 1.).unwrap()[0];
    assert!((screen[0] - 0.28).abs() < 1e-6 && (screen[3] - 0.6).abs() < 1e-6);
    p[19] = 1.;
    let add = render(&src, &p, 0., 1.).unwrap()[0];
    assert!((add[0] - 0.3).abs() < 1e-6 && add[3] == screen[3]);
}
#[test]
fn chromatic_channels_and_static_noise_do_not_modify_unselected_channels() {
    let mut src = img();
    for (i, px) in src.pixels.iter_mut().enumerate() {
        let c = (i % 8) as f32 / 8.;
        *px = [c, c, c, 1.];
    }
    let mut p = params();
    p[20] = 0.;
    let original = render(&src, &p, 0., 1.).unwrap();
    p[11] = 100.;
    for pair in 0..3 {
        p[12] = pair as f64;
        let other = [1, 2, 0][pair];
        let changed = render(&src, &p, 0., 1.).unwrap();
        assert_ne!(changed, original);
        assert!(
            changed
                .iter()
                .zip(&original)
                .all(|(a, b)| a[other] == b[other])
        );
    }
    p[11] = 0.;
    p[14] = 16.;
    p[15] = 100.;
    let first = render(&src, &p, 0., 1.).unwrap();
    assert_eq!(first, render(&src, &p, 100., 1.).unwrap());
    p[15] = 0.;
    assert_ne!(first, render(&src, &p, 0., 1.).unwrap());
    p[15] = 100.;
    assert_eq!(first, render(&src, &p, 0., 1.).unwrap());
    assert_eq!(
        [0., 1., 2., 3.].map(|q| {
            p[13] = q;
            count(&p)
        }),
        [8, 16, 32, 64]
    );
    p[13] = 4.;
    p[14] = 3.6;
    assert_eq!(count(&p), 4);
}
#[test]
fn trim_and_scale_use_real_geometry() {
    let mut src = img();
    src.pixels.fill([1.; 4]);
    let mut p = params();
    p[21] = 0.;
    p[22] = 2.;
    let full = render(&src, &p, 0., 1.).unwrap();
    assert_eq!(full[0], [0.; 4]);
    assert_eq!(full[1], [0.; 4]);
    assert_eq!(full[2], [1.; 4]);
    src.w = 4;
    src.h = 2;
    src.pixels = vec![[1.; 4]; 8];
    src.geo.scale = 0.5;
    let half = render(&src, &p, 0., 0.5).unwrap();
    assert_eq!(half[0], [0.; 4]);
    assert_eq!(half[1], [1.; 4]);
    src.geo.offset[0] = 1.;
    assert_eq!(render(&src, &p, 0., 0.5).unwrap()[1], [0.; 4]);
}
#[test]
fn malformed_params_geometry_and_expansion_refused_before_output() {
    let src = img();
    let p = params();
    for (i, v) in [
        (0, 2.),
        (1, 1e7),
        (4, -1.),
        (6, 100001.),
        (7, 360001.),
        (8, 21.),
        (9, 11.),
        (10, 3.),
        (13, 5.),
        (14, 1.),
        (16, 2.),
        (17, 1.),
        (18, 101.),
        (20, 2.),
        (22, 8193.),
        (8, f64::NAN),
    ] {
        let mut bad = p;
        bad[i] = v;
        assert!(render(&src, &bad, 0., 1.).is_err(), "{i}");
    }
    assert!(render(&src, &p[..25], 0., 1.).is_err());
    assert!(render(&src, &p, f64::INFINITY, 1.).is_err());
    assert!(render(&src, &p, 0., 0.5).is_err());
    let mut bad = img();
    bad.geo.size[0] = f64::NAN;
    assert!(render(&bad, &p, 0., 1.).is_err());
    let mut bad = img();
    bad.pixels[0][3] = 2.;
    assert!(render(&bad, &p, 0., 1.).is_err());
}
#[test]
fn descriptor_requires_exact_offsets_reserved_fields_and_finite_rgba() {
    let size = FLAT * 8 + 80;
    let mut data = vec![0u8; size + 16];
    data[FLAT * 8..FLAT * 8 + 4].copy_from_slice(&u32::MAX.to_le_bytes());
    for (off, value) in [(12, 1u32), (16, size as u32), (20, 1), (24, 1)] {
        data[FLAT * 8 + off..FLAT * 8 + off + 4].copy_from_slice(&value.to_le_bytes());
    }
    for off in [48, 56, 64] {
        data[FLAT * 8 + off..FLAT * 8 + off + 8].copy_from_slice(&1f64.to_le_bytes());
    }
    data[size + 12..size + 16].copy_from_slice(&1f32.to_le_bytes());
    assert!(image(&data, 0, 0, size, u32::MAX, [0, 0], true).is_ok());
    for off in [28, 72, 76] {
        let mut bad = data.clone();
        bad[FLAT * 8 + off] = 1;
        assert!(image(&bad, 0, 0, size, u32::MAX, [0, 0], true).is_err());
    }
    data[size..size + 4].copy_from_slice(&f32::NAN.to_le_bytes());
    assert!(image(&data, 0, 0, size, u32::MAX, [0, 0], true).is_err());
}

#[test]
fn host_point_transform_is_inverted_for_half_resolution_and_padding() {
    let mut src = img();
    src.geo.size = [16., 8.];
    src.geo.scale = 0.5;
    let mut p = params();
    p[1] = 1. / 32. * 0.5;
    p[2] = 1. / 16. * 0.5;
    assert_eq!(center(&src, &p).unwrap(), [8.5, 4.5]);
    let out = render(&src, &p, 0., 0.5).unwrap();
    assert_eq!(out[0], [0.28125, 0., 0., 0.28125]);
    assert_eq!(out[20], [0.78125, 0., 0., 0.78125]);
    src.geo.offset = [3., -2.];
    p[1] += 3.;
    p[2] -= 2.;
    assert_eq!(center(&src, &p).unwrap(), [8.5, 4.5]);
}
