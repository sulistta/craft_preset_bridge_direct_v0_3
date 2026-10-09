use super::*;
fn params() -> [f64; FLAT] {
    [
        7., 0., 100., 4., 0., 100., 100., 1., 0., 0., 1., 0., 0., 1., 1., 0., 0., 0., 50., 1., 7.,
        0.,
    ]
}
fn image() -> Image {
    Image {
        w: 32,
        h: 32,
        geo: Geometry {
            offset: [0.; 2],
            scale: 1.,
            size: [32., 32.],
        },
        pixels: vec![[0.5, 0.5, 0.5, 0.5]; 1024],
    }
}
#[test]
fn ten_patterns_are_original_distinct_masks() {
    let img = image();
    let mut outputs = Vec::new();
    for shape in 0..10 {
        let mut p = params();
        p[0] = shape as f64;
        p[3] = 16.;
        let out = render(&img, &p, 0., 1.).unwrap();
        assert!(out.iter().any(|x| x[0] > 0.), "{shape}");
        assert!(out.iter().any(|x| x[2] > 0.), "{shape}");
        outputs.push(out);
    }
    for a in 0..10 {
        for b in a + 1..10 {
            assert_ne!(outputs[a], outputs[b], "{a},{b}");
        }
    }
}
#[test]
fn brightness_and_contrast_have_independent_math() {
    let img = image();
    let mut p = params();
    p[1] = -100.;
    assert!(
        render(&img, &p, 0., 1.)
            .unwrap()
            .iter()
            .all(|c| *c == [0., 0., 1., 0.5])
    );
    p[1] = 100.;
    assert!(
        render(&img, &p, 0., 1.)
            .unwrap()
            .iter()
            .all(|c| *c == [1., 0., 0., 0.5])
    );
    p[1] = 0.;
    p[2] = 0.;
    let a = render(&img, &p, 0., 1.).unwrap();
    let mut q = image();
    q.pixels.fill([0.1, 0.1, 0.1, 0.5]);
    assert_eq!(a, render(&q, &p, 0., 1.).unwrap());
}
#[test]
fn original_color_transparency_and_alpha_are_respected() {
    let img = image();
    let mut p = params();
    p[15] = 1.;
    p[16] = 1.;
    let out = render(&img, &p, 0., 1.).unwrap();
    assert!(out.contains(&[0.; 4]));
    assert!(out.contains(&[0.5, 0.5, 0.5, 0.25]));
    p[15] = 0.;
    p[10] = 0.2;
    assert!(
        render(&img, &p, 0., 1.)
            .unwrap()
            .iter()
            .any(|x| x[3] == 0.1)
    );
}
#[test]
fn anisotropy_lock_and_tile_size_change_patterns() {
    let img = image();
    let p = params();
    let base = render(&img, &p, 0., 1.).unwrap();
    for (i, v) in [(3, 8.), (5, 50.), (6, 50.)] {
        let mut q = p;
        q[i] = v;
        assert_ne!(base, render(&img, &q, 0., 1.).unwrap(), "{i}");
    }
    let mut q = p;
    q[4] = 1.;
    q[6] = 5.;
    assert_eq!(base, render(&img, &q, 0., 1.).unwrap());
}
#[test]
fn chaos_behaviors_and_fractional_seed_are_deterministic() {
    let img = image();
    let mut p = params();
    p[17] = 1.;
    p[18] = 90.;
    let base = render(&img, &p, 0., 1.).unwrap();
    assert_eq!(base, render(&img, &p, 0., 1.).unwrap());
    for behavior in [1., 2.] {
        let mut q = p;
        q[21] = behavior;
        assert_ne!(base, render(&img, &q, 0., 1.).unwrap());
    }
    p[20] += 0.25;
    assert_ne!(base, render(&img, &p, 0., 1.).unwrap());
    assert_ne!(
        render(&img, &p, 0., 1.).unwrap(),
        render(&img, &p, 3., 1.).unwrap()
    );
    p[19] = 0.;
    assert_eq!(
        render(&img, &p, 0., 1.).unwrap(),
        render(&img, &p, 3., 1.).unwrap()
    );
}
#[test]
fn invalid_values_refuse_complete_render() {
    let img = image();
    for (i, v) in [(0, 10.), (3, 0.), (10, 2.), (19, 10001.), (20, f64::NAN)] {
        let mut p = params();
        p[i] = v;
        assert!(render(&img, &p, 0., 1.).is_err());
    }
    assert!(render(&img, &params(), 0., 0.).is_err());
}
