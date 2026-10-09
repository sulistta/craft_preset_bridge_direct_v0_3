use super::*;
fn params() -> [f64; FLAT] {
    [
        0., 0., 0., 0., 0.125, 0., 0., 0., 1., 1., 1., 1., 0., 0., 0.,
    ]
}
fn image(c: Pixel, w: usize, h: usize) -> Image {
    Image {
        pixels: vec![c; w * h],
        w,
        h,
        geo: Geometry {
            offset: [0.; 2],
            scale: 1.,
        },
    }
}
#[test]
fn threshold_preserves_rgb_ratios_above_peak_and_zeroes_below() {
    let p = params();
    let out = extract([0.5, 0.25, 0.125, 1.], &p);
    assert_eq!(out, [0.375, 0.1875, 0.09375, 1.]);
    assert_eq!(extract([0.1, 0.1, 0.1, 1.], &p), [0., 0., 0., 1.]);
}
#[test]
fn additive_color_bias_saturation_and_brightness_act_independently() {
    let mut p = params();
    p[5] = 1.;
    assert_eq!(extract([0.5, 0., 0., 1.], &p), [0., 0., 0., 1.]);
    assert_eq!(extract([0., 0., 0.5, 1.], &p), [0., 0., 0.375, 1.]);
    p[5] = 0.;
    p[9] = 0.;
    assert_eq!(
        extract([0.5, 0.25, 0.125, 1.], &p),
        [0.2109375, 0.2109375, 0.2109375, 1.]
    );
}
#[test]
fn opacity_modes_and_hidden_rgb_have_explicit_contract() {
    let mut p = params();
    assert_eq!(
        extract([0.25, 0.25, 0.25, 0.5], &p),
        [0.1875, 0.1875, 0.1875, 0.5]
    );
    assert_eq!(extract([1., 1., 1., 0.], &p), [0.; 4]);
    p[11] = 2.;
    assert_eq!(
        extract([0.25, 0.25, 0.25, 0.5], &p),
        [0.125, 0.125, 0.125, 0.5]
    );
    p[11] = 0.;
    assert_eq!(
        extract([0.25, 0.25, 0.25, 0.5], &p),
        [0.125, 0.125, 0.125, 1.]
    );
}
#[test]
fn black_white_alpha_and_inverted_mask_have_analytic_results() {
    let main = image([0.5, 0.5, 0.5, 1.], 2, 2);
    let white = image([1.; 4], 2, 2);
    let black = image([0., 0., 0., 1.], 2, 2);
    let mut p = params();
    assert_eq!(
        render(&main, Some(&black), &p, 0., 1.).unwrap(),
        main.pixels
    );
    assert_eq!(
        render(&main, Some(&white), &p, 0., 1.).unwrap(),
        vec![[0.375, 0.375, 0.375, 1.]; 4]
    );
    p[12] = 1.;
    assert_eq!(
        render(&main, Some(&black), &p, 0., 1.).unwrap(),
        vec![[0.375, 0.375, 0.375, 1.]; 4]
    );
    p[14] = 1.;
    assert_eq!(
        render(&main, Some(&black), &p, 0., 1.).unwrap(),
        main.pixels
    );
}
#[test]
fn fractional_blur_matches_direct_separable_filter() {
    let src = [0., 0., 1., 0., 0.];
    let mut dst = [0.; 5];
    box_axis(&src, &mut dst, 5, 1, 1.5, true);
    assert_eq!(dst, [0.125, 0.25, 0.25, 0.25, 0.125]);
    let img = image([0.3, 0.2, 0.1, 0.5], 3, 2);
    assert_eq!(blur(&img, 17.25).unwrap(), img.pixels);
}
#[test]
fn input_and_mask_blurs_change_the_correct_image() {
    let mut main = image([0., 0., 0., 1.], 9, 9);
    main.pixels[40] = [1.; 4];
    let mut p = params();
    let original = render(&main, None, &p, 0., 1.).unwrap();
    p[3] = 1.;
    assert_ne!(original, render(&main, None, &p, 0., 1.).unwrap());
    p[3] = 0.;
    let mut mask = image([0., 0., 0., 1.], 9, 9);
    mask.pixels[40] = [1.; 4];
    let before = render(&main, Some(&mask), &p, 0., 1.).unwrap();
    p[13] = 1.;
    assert_ne!(before, render(&main, Some(&mask), &p, 0., 1.).unwrap());
}
#[test]
fn invalid_values_refuse_whole_render_and_no_mask_ignores_invert_blur() {
    let img = image([0.5; 4], 1, 1);
    for (i, v) in [(0, -1.), (3, 8193.), (11, 3.), (4, f64::NAN)] {
        let mut p = params();
        p[i] = v;
        assert!(render(&img, None, &p, 0., 1.).is_err());
    }
    let mut p = params();
    let before = render(&img, None, &p, 0., 1.).unwrap();
    p[13] = 12.;
    p[14] = 1.;
    assert_eq!(before, render(&img, None, &p, 0., 1.).unwrap());
}
