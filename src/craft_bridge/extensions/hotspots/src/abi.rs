thread_local! {static HOST:RefCell<Vec<u64>>=const {RefCell::new(Vec::new())};}
#[unsafe(no_mangle)]
pub extern "C" fn ec_api_version() -> i32 {
    2
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_ptr() -> i32 {
    MANIFEST.as_ptr() as i32
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_len() -> i32 {
    MANIFEST.len() as i32
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_alloc(bytes: i32) -> i32 {
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 * 2 + FLAT * 8 + 160 {
        return 0;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let n = (bytes as usize).div_ceil(8);
        let extra = n.saturating_sub(host.len());
        if host.try_reserve(extra).is_err() {
            return 0;
        }
        host.resize(n, 0);
        host.as_mut_ptr() as i32
    })
}
fn u32at(data: &[u8], off: usize) -> Result<u32, ()> {
    Ok(u32::from_le_bytes(
        data.get(off..off + 4)
            .ok_or(())?
            .try_into()
            .map_err(|_| ())?,
    ))
}
fn f64at(data: &[u8], off: usize) -> Result<f64, ()> {
    Ok(f64::from_le_bytes(
        data.get(off..off + 8)
            .ok_or(())?
            .try_into()
            .map_err(|_| ())?,
    ))
}
fn image(
    data: &[u8],
    base: usize,
    entry: usize,
    expected: usize,
    decl: u32,
    uid: [u32; 2],
    main: bool,
) -> Result<(Option<Image>, usize), ()> {
    let d = FLAT * 8 + entry * 80;
    if u32at(data, d)? != decl
        || [u32at(data, d + 4)?, u32at(data, d + 8)?] != uid
        || u32at(data, d + 28)? != 0
        || u32at(data, d + 72)? != 0
        || u32at(data, d + 76)? != 0
    {
        return Err(());
    }
    let flag = u32at(data, d + 12)?;
    if !main && uid == [0, 0] {
        if flag != 0
            || data[d + 16..d + 28].iter().any(|v| *v != 0)
            || data[d + 32..d + 72].iter().any(|v| *v != 0)
        {
            return Err(());
        }
        return Ok((None, expected));
    }
    if flag != if main { 1 } else { 2 } || (!main && uid == [0, 0]) {
        return Err(());
    }
    let ptr = u32at(data, d + 16)? as usize;
    let w = u32at(data, d + 20)? as usize;
    let h = u32at(data, d + 24)? as usize;
    let n = w
        .checked_mul(h)
        .filter(|n| *n > 0 && *n <= MAX_PIXELS)
        .ok_or(())?;
    let end = expected
        .checked_add(n * 16)
        .filter(|v| *v <= data.len())
        .ok_or(())?;
    if ptr != base + expected || w > 65536 || h > 65536 {
        return Err(());
    }
    let geo = Geometry {
        offset: [f64at(data, d + 32)?, f64at(data, d + 40)?],
        scale: f64at(data, d + 48)?,
    };
    if geo.offset.iter().any(|v| !v.is_finite() || v.abs() > 1e9)
        || !geo.scale.is_finite()
        || !(1.0 / 65536.0..=16.0).contains(&geo.scale)
    {
        return Err(());
    }
    for offset in [56, 64] {
        let v = f64at(data, d + offset)?;
        if !v.is_finite() || !(f64::MIN_POSITIVE..=1e9).contains(&v) {
            return Err(());
        }
    }
    let mut pixels: Vec<Pixel> = zeros(n)?;
    for (px, bytes) in pixels
        .iter_mut()
        .zip(data[expected..end].as_chunks::<16>().0)
    {
        for ch in 0..4 {
            px[ch] = f32::from_le_bytes(bytes[ch * 4..ch * 4 + 4].try_into().map_err(|_| ())?);
        }
        if px.iter().any(|v| !v.is_finite() || v.abs() > 1e6) || !(0.0..=1.0).contains(&px[3]) {
            return Err(());
        }
    }
    Ok((Some(Image { pixels, w, h, geo }), end))
}
#[unsafe(no_mangle)]
#[allow(clippy::too_many_arguments)]
pub extern "C" fn ec_render_v2(
    pixels: i32,
    w: i32,
    h: i32,
    params: i32,
    nparams: i32,
    time: f64,
    scale: f64,
    table: i32,
    entries: i32,
) -> i32 {
    if nparams != FLAT as i32 || entries != 2 || w <= 0 || h <= 0 {
        return 1;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let base = host.as_mut_ptr() as usize;
        if params as u32 as usize != base
            || table as u32 as usize != base + FLAT * 8
            || pixels as u32 as usize != base + FLAT * 8 + 160
        {
            return 1;
        }
        // Only parse the checked allocation; copy images before committing any pixels.
        let data =
            unsafe { std::slice::from_raw_parts(host.as_ptr() as *const u8, host.len() * 8) };
        let attempt = (|| -> Result<Vec<Pixel>, ()> {
            let mut p = [0.0; FLAT];
            for (i, v) in p.iter_mut().enumerate() {
                *v = f64at(data, i * 8)?;
            }
            if !valid(&p, time, scale) {
                return Err(());
            }
            let (main, next) = image(data, base, 0, FLAT * 8 + 160, u32::MAX, [0, 0], true)?;
            let main = main.ok_or(())?;
            if main.w != w as usize || main.h != h as usize || main.geo.scale != scale {
                return Err(());
            }
            let (mask, _) = image(data, base, 1, next, 0, [p[0] as u32, p[1] as u32], false)?;
            render(&main, mask.as_ref(), &p, time, scale)
        })();
        let Ok(out) = attempt else {
            return 1;
        };
        let dst = unsafe {
            std::slice::from_raw_parts_mut((base + FLAT * 8 + 160) as *mut Pixel, out.len())
        };
        dst.copy_from_slice(&out);
        0
    })
}

