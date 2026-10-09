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
