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
fn box_axis(src: &[f64], dst: &mut [f64], w: usize, h: usize, r: f64, horizontal: bool) {
    let n = r.floor() as isize;
    let f = r - n as f64;
    let (len, lines, step) = if horizontal { (w, h, 1) } else { (h, w, w) };
    for line in 0..lines {
        let base = if horizontal { line * w } else { line };
        let at = |x: isize| src[base + x.clamp(0, len as isize - 1) as usize * step];
        let mut sum =
            at(0) * (n + 1) as f64 + at(len as isize - 1) * (n - (len as isize - 1)).max(0) as f64;
        for x in 1..=n.min(len as isize - 1) {
            sum += at(x);
        }
        for x in 0..len {
            dst[base + x * step] =
                (sum + f * (at(x as isize - n - 1) + at(x as isize + n + 1))) / (2.0 * r + 1.0);
            sum += at(x as isize + n + 1) - at(x as isize - n);
        }
    }
}
