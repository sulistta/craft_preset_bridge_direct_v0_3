use super::*;
fn image(w: usize, h: usize) -> Image {
    Image {
        w,
        h,
        geo: Geometry {
            offset: [0.; 2],
            scale: 1.,
            size: [w as f64, h as f64],
        },
        pixels: vec![[0.5, 0.25, 0.125, 1.]; w * h],
    }
}
fn params() -> [f64; FLAT] {
    [
        0., 0., 0., 12., 1., 8., 4., 1.75, 0., 100., 0., 180., 180., 95., 0., 40., 0., 255., 1.,
        0., 777.,
    ]
}
#[test]
fn analytic_alpha_compositing_and_zero_coverage() {
    let mut dst = [0., 0., 1., 0.5];
    blend(&mut dst, [1., 0., 0., 0.5], 1.);
    assert_eq!(dst, [2. / 3., 0., 1. / 3., 0.75]);
    let old = dst;
    blend(&mut dst, [7., 4., 2., 1.], 0.);
    assert_eq!(dst, old);
}
#[test]
fn line_polygon_circle_geometry_agree_with_analytic_points() {
    assert_eq!(segment([2., 3.], [0., 0.], [4., 0.]), 3.);
    assert_eq!(segment([5., 0.], [0., 0.], [4., 0.]), 1.);
    let square = [[0., 0.], [4., 0.], [4., 4.], [0., 4.]];
    assert!(polygon([2., 2.], &square, true, 0.));
    assert!(!polygon([2., 2.], &square, false, 1.));
    assert!(polygon([0.25, 2.], &square, false, 1.));
    assert!(!polygon([5., 2.], &square, true, 1.));
}
#[test]
fn six_shapes_draw_and_preserve_color_without_original_background() {
    let img = image(64, 64);
    let p = params();
    let mut results = vec![];
    for shape in 0..6 {
        let mut q = p;
        q[2] = shape as f64;
        q[8] = 1.;
        let out = render(&img, &q, 0., 1., 1. / 30.).unwrap();
        assert!(out.iter().any(|p| p[3] > 0.));
        assert!(out.iter().any(|p| p[3] == 0.));
        assert!(
            out.iter()
                .filter(|p| p[3] > 0.)
                .all(|p| p[..3] == [0.5, 0.25, 0.125])
        );
        results.push(out);
    }
    for i in 0..6 {
        for j in i + 1..6 {
            assert_ne!(results[i], results[j], "{i}, {j}");
        }
    }
}
#[test]
fn opacity_fill_line_width_and_fades_have_distinct_outputs() {
    let img = image(64, 64);
    let mut p = params();
    p[2] = 3.;
    let baseline = render(&img, &p, 0., 1., 1. / 30.).unwrap();
    for (index, value) in [(7, 4.), (8, 1.), (9, 25.), (14, 2.)] {
        let mut q = p;
        q[index] = value;
        assert_ne!(
            render(&img, &q, 0., 1., 1. / 30.).unwrap(),
            baseline,
            "{index}"
        );
    }
    p[4] = 3.;
    let base = render(&img, &p, 0., 1., 1. / 30.).unwrap();
    for fade in [3., 4.] {
        p[14] = fade;
        assert_ne!(render(&img, &p, 0., 1., 1. / 30.).unwrap(), base);
    }
}
#[test]
fn deterministic_seed_stable_random_and_random_source_clock() {
    let img = image(64, 64);
    let mut p = params();
    let a = render(&img, &p, 0., 1., 1. / 30.).unwrap();
    assert_eq!(render(&img, &p, 3., 1., 1. / 30.).unwrap(), a);
    p[20] += 1.;
    assert_ne!(render(&img, &p, 0., 1., 1. / 30.).unwrap(), a);
    p[18] = 0.;
    assert_ne!(
        render(&img, &p, 0., 1., 1. / 30.).unwrap(),
        render(&img, &p, 1., 1., 1. / 30.).unwrap()
    );
}
#[test]
fn matching_follows_same_color_and_refuses_incompatible_endpoint() {
    let mut img = image(20, 10);
    for y in 0..10 {
        for x in 10..20 {
            img.pixels[y * 20 + x] = [0., 0., 1., 1.];
        }
    }
    let mut budget = Budget {
        visits: 0,
        probes: 0,
    };
    let color = sample(&img, [5., 5.]);
    assert!(
        endpoint(&img, [5., 5.], color, 0., 10., 0., 0., 100., &mut budget)
            .unwrap()
            .is_none()
    );
    assert!(
        endpoint(
            &img,
            [5., 5.],
            color,
            TAU / 2.,
            2.,
            0.,
            0.,
            100.,
            &mut budget
        )
        .unwrap()
        .is_some()
    );
    assert!(
        endpoint(&img, [5., 5.], color, 0., 10., 0., 0., 0., &mut budget)
            .unwrap()
            .is_some()
    );
}
#[test]
fn empty_ranges_and_disabled_shapes_respect_keep_original() {
    let img = image(16, 16);
    for (i, value) in [(3, 0.), (4, 0.), (5, 0.), (9, 0.), (16, 200.)] {
        let mut p = params();
        p[i] = value;
        assert!(
            render(&img, &p, 0., 1., 1. / 30.)
                .unwrap()
                .iter()
                .all(|x| x == &[0.; 4])
        );
        p[0] = 1.;
        assert_eq!(render(&img, &p, 0., 1., 1. / 30.).unwrap(), img.pixels);
    }
}
#[test]
fn fractional_counts_and_recursion_are_documented_floor() {
    let img = image(32, 32);
    let p = params();
    let mut q = p;
    q[3] += 0.9;
    q[4] += 0.9;
    assert_eq!(
        render(&img, &p, 0., 1., 1. / 30.).unwrap(),
        render(&img, &q, 0., 1., 1. / 30.).unwrap()
    );
}
#[test]
fn budgets_and_invalid_inputs_refuse_instead_of_partial_success() {
    let img = image(32, 32);
    let mut p = params();
    for (i, v) in [(1, 0.5), (2, 6.), (3, 10001.), (4, 17.), (20, f64::NAN)] {
        let mut q = p;
        q[i] = v;
        assert!(render(&img, &q, 0., 1., 1. / 30.).is_err());
    }
    p[3] = 10000.;
    p[4] = 16.;
    p[5] = 1.;
    p[6] = 0.;
    p[13] = 0.;
    assert!(render(&img, &p, 0., 1., 1. / 30.).is_err());
    assert!(render(&img, &params(), 0., 1., 0.).is_err());
}
#[test]
fn preview_geometry_preserves_original_local_size() {
    let full = image(32, 32);
    let mut half = image(16, 16);
    half.geo.scale = 0.5;
    half.geo.size = [32., 32.];
    let p = params();
    let a = render(&full, &p, 0., 1., 1. / 30.).unwrap();
    let b = render(&half, &p, 0., 0.5, 1. / 30.).unwrap();
    assert!(a.iter().any(|x| x[3] > 0.));
    assert!(b.iter().any(|x| x[3] > 0.));
    assert!(a.iter().chain(&b).all(|x| x.iter().all(|v| v.is_finite())));
}
