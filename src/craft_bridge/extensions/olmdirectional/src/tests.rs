use super::*;
fn params() -> [f64; FLAT] {
    [
        0., 0., 0., 0., 1., 0., 2., 0., 0., 0., 0., 0., 0., 0., 1., 0., 10.,
    ]
}
fn image(w: usize, h: usize) -> Image {
    Image {
        pixels: vec![[0.; 4]; w * h],
        w,
        h,
        geo: Geometry {
            offset: [0., 0.],
            scale: 1.,
        },
    }
}
fn impulse() -> Image {
    let mut img = image(5, 5);
    img.pixels[12] = [1., 0., 0., 1.];
    img
}
#[test]
fn front_and_back_are_independent_and_do_not_dilute_color() {
    let img = impulse();
    let p = params();
    let out = render(&img, None, &p, 0., 1.).unwrap();
    assert_eq!(out[13], [1., 0., 0., 1.]);
    assert_eq!(out[14], [1., 0., 0., 1.]);
    assert_eq!(out[11], [0.; 4]);
    let mut p = p;
    p[6] = 0.;
    p[9] = 2.;
    let out = render(&img, None, &p, 0., 1.).unwrap();
    assert_eq!(out[10], [1., 0., 0., 1.]);
    assert_eq!(out[14], [0.; 4]);
}
#[test]
fn ninety_degree_angle_and_half_resolution_are_geometric() {
    let img = impulse();
    let mut p = params();
    p[3] = 90.;
    let out = render(&img, None, &p, 0., 1.).unwrap();
    assert_eq!(out[22], [1., 0., 0., 1.]);
    assert_eq!(out[14], [0.; 4]);
    let mut img = img;
    img.geo.scale = 0.5;
    p[3] = 0.;
    let out = render(&img, None, &p, 0., 0.5).unwrap();
    assert_eq!(out[13], [1., 0., 0., 1.]);
    assert_eq!(out[14], [0.; 4]);
}
#[test]
fn alpha_fade_and_brightness_preserve_premultiplication() {
    let img = impulse();
    let mut p = params();
    p[7] = 100.;
    p[4] = 2.;
    let out = render(&img, None, &p, 0., 1.).unwrap();
    assert_eq!(out[12], [2., 0., 0., 1.]);
    assert_eq!(out[13], [1., 0., 0., 0.5]);
    assert_eq!(out[14], [0.; 4]);
}
#[test]
fn layer_noise_brightness_modulates_length() {
    let img = impulse();
    let mut p = params();
    p[13] = 2.;
    p[12] = 100.;
    let mut noise = image(5, 5);
    noise.pixels.fill([0., 0., 0., 1.]);
    let out = render(&img, Some(&noise), &p, 0., 1.).unwrap();
    assert_eq!(out, img.pixels);
    noise.pixels.fill([1.; 4]);
    let out = render(&img, Some(&noise), &p, 0., 1.).unwrap();
    assert_eq!(out[14], [1., 0., 0., 1.]);
    noise.pixels.fill([0.5, 0.5, 0.5, 1.]);
    let out = render(&img, Some(&noise), &p, 0., 1.).unwrap();
    assert_eq!(out[13], [1., 0., 0., 1.]);
    assert_eq!(out[14], [0.; 4]);
}
#[test]
fn noise_types_seed_and_offset_are_deterministic() {
    let mut p = params();
    let point = [2.5, 2.5];
    let perp = [0., 1.];
    p[16] = 1.;
    let a = noise_at(None, point, perp, &p);
    assert!((0. ..=1.).contains(&a));
    p[13] = 1.;
    let b = noise_at(None, point, perp, &p);
    assert_ne!(a, b);
    p[14] = 2.;
    assert_ne!(b, noise_at(None, point, perp, &p));
    p[13] = 0.;
    let a = noise_at(None, point, perp, &p);
    p[15] = 1.;
    assert_ne!(a, noise_at(None, point, perp, &p));
    let img = impulse();
    assert_eq!(
        render(&img, None, &p, 0., 1.).unwrap(),
        render(&img, None, &p, 9., 1.).unwrap()
    );
}
#[test]
fn size_variation_uses_connected_groups_and_removes_smallest_blur() {
    let mut img = image(9, 9);
    img.pixels[10] = [1.; 4];
    for y in 5..8 {
        for x in 5..8 {
            img.pixels[y * 9 + x] = [1.; 4];
        }
    }
    let groups = components(&img, [0., 1.]).unwrap();
    assert_eq!(groups.groups.len(), 2);
    assert_eq!((groups.min, groups.max), (1, 9));
    assert_eq!(size_factor(&groups.groups[0], &groups, 100.), 0.);
    assert_eq!(size_factor(&groups.groups[1], &groups, 100.), 1.);
    let mut p = params();
    p[5] = 100.;
    let out = render(&img, None, &p, 0., 1.).unwrap();
    assert_eq!(out[11], [0.; 4]);
    assert_eq!(out[6 * 9 + 8], [1.; 4]);
}
#[test]
fn sharp_tail_tapers_each_group_toward_its_centerline() {
    let mut img = image(7, 5);
    for y in 1..4 {
        img.pixels[y * 7 + 1] = [1.; 4];
    }
    let mut p = params();
    p[6] = 3.;
    p[8] = 100.;
    let out = render(&img, None, &p, 0., 1.).unwrap();
    assert_eq!(out[2 * 7 + 4], [1.; 4]);
    assert_eq!(out[7 + 4], [0.; 4]);
    assert_eq!(out[3 * 7 + 4], [0.; 4]);
}
#[test]
fn hidden_rgb_and_opaque_detail_are_preserved_correctly() {
    let mut img = impulse();
    img.pixels[0] = [1e6, -1e6, 1e6, 0.];
    img.pixels[13] = [0., 1., 0., 1.];
    let out = render(&img, None, &params(), 0., 1.).unwrap();
    assert_eq!(out[0], [0.; 4]);
    assert_eq!(out[13], [0., 1., 0., 1.]);
}
#[test]
fn invalid_bounds_and_active_layer_geometry_are_refused() {
    let img = impulse();
    let p = params();
    for (i, v) in [
        (6, 4001.),
        (5, 101.),
        (13, 3.),
        (16, 0.),
        (0, 0.5),
        (4, f64::NAN),
    ] {
        let mut bad = p;
        bad[i] = v;
        assert!(render(&img, None, &bad, 0., 1.).is_err());
    }
    let mut p = p;
    p[13] = 2.;
    assert!(render(&img, Some(&image(2, 2)), &p, 0., 1.).is_err());
}
