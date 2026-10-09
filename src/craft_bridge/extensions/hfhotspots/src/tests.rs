use super::*;
fn params() -> [f64; FLAT] {
    [0.5, 0., 0., 0., 1., 1., 1., 0.]
}
fn image(pixels: Vec<Pixel>) -> Image {
    Image {
        w: pixels.len(),
        h: 1,
        pixels,
        geo: Geometry {
            offset: [0., 0.],
            scale: 1.,
            size: [3., 1.],
        },
    }
}
#[test]
fn threshold_gate_preserves_highlights_instead_of_subtracting() {
    let p = params();
    assert_eq!(gate([0.75, 0.5, 0.25, 1.], &p), [0.75, 0.5, 0.25, 1.]);
    assert_eq!(gate([0.25; 4], &p), [0.25; 4]);
    assert_eq!(gate([0.4, 0.2, 0.1, 1.], &p), [0., 0., 0., 1.]);
}
#[test]
fn subthreshold_fill_includes_color_alpha() {
    let mut p = params();
    p[1] = 1.;
    p[3] = 0.5;
    p[4] = 0.25;
    assert_eq!(gate([0.1, 0., 0., 0.5], &p), [0.125, 0., 0.0625, 0.125]);
}
#[test]
fn saturation_and_brightness_only_change_highlights() {
    let mut p = params();
    p[5] = 0.;
    p[6] = 2.;
    assert_eq!(gate([1., 0., 0., 1.], &p), [0.5, 0.5, 0.5, 1.]);
    assert_eq!(gate([0.1, 0., 0., 1.], &p), [0., 0., 0., 1.]);
}
#[test]
fn hidden_rgb_and_zero_alpha_never_leak() {
    let p = params();
    assert_eq!(gate([1e6, -1e6, 1e6, 0.], &p), [0.; 4]);
}
#[test]
fn smoothing_before_gate_changes_impulse_and_honors_scale() {
    let src = image(vec![[0., 0., 0., 1.], [1., 1., 1., 1.], [0., 0., 0., 1.]]);
    let mut p = params();
    p[7] = 1.;
    assert!(
        render(&src, &p, 0., 1.)
            .unwrap()
            .iter()
            .all(|v| *v == [0., 0., 0., 1.])
    );
    p[0] = 0.2;
    let result = render(&src, &p, 0., 1.).unwrap();
    assert!(result.iter().all(|v| (v[0] - 1. / 3.).abs() < 1e-6));
    let mut half = image(src.pixels.clone());
    half.geo.scale = 0.5;
    p[0] = 0.4;
    let result = render(&half, &p, 0., 0.5).unwrap();
    assert_eq!(result[0], [0., 0., 0., 1.]);
    assert_eq!(result[1], [0.5, 0.5, 0.5, 1.]);
}
#[test]
fn invalid_requests_refused_and_uniform_large_radius_finite() {
    let src = image(vec![[0.75, 0.5, 0.25, 1.]; 3]);
    let p = params();
    for (i, v) in [
        (0, -1.),
        (4, 2.),
        (5, 65.),
        (6, -1.),
        (7, 8193.),
        (0, f64::NAN),
    ] {
        let mut bad = p;
        bad[i] = v;
        assert!(render(&src, &bad, 0., 1.).is_err());
    }
    assert!(render(&src, &p, f64::INFINITY, 1.).is_err());
    let mut p = p;
    p[7] = 8192.;
    assert_eq!(render(&src, &p, 0., 1.).unwrap(), src.pixels);
}
