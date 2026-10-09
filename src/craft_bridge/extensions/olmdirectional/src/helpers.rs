fn sample(image: Option<&Image>, layer: [f64; 2]) -> Pixel {
    let Some(img) = image else {
        return [0.0; 4];
    };
    // Pixel centers transformed through each buffer's documented geometry.
    let x = layer[0] * img.geo.scale + img.geo.offset[0] - 0.5;
    let y = layer[1] * img.geo.scale + img.geo.offset[1] - 0.5;
    if x < -1.0 || y < -1.0 || x >= img.w as f64 || y >= img.h as f64 {
        return [0.0; 4];
    }
    let ix = x.floor() as isize;
    let iy = y.floor() as isize;
    let fx = x - ix as f64;
    let fy = y - iy as f64;
    let mut out = [0.0f64; 4];
    for (dx, wx) in [(0, 1.0 - fx), (1, fx)] {
        for (dy, wy) in [(0, 1.0 - fy), (1, fy)] {
            let xx = ix + dx;
            let yy = iy + dy;
            if xx >= 0 && yy >= 0 && xx < img.w as isize && yy < img.h as isize {
                let px = img.pixels[yy as usize * img.w + xx as usize];
                for ch in 0..4 {
                    out[ch] += px[ch] as f64 * wx * wy;
                }
            }
        }
    }
    out.map(|v| v as f32)
}
