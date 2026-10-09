//! Original procedural OFP scene renderer, EffectCraft API v1.
//! Exact input bytes; explicitly approximate kernels/calibration. No assets or imports.

use std::cell::RefCell;
use std::f64::consts::{PI, TAU};

const SCENE_CAPACITY: usize = 2 * 1024 * 1024;
const MANIFEST_CAPACITY: usize = 16 * 1024;
const FLAT: usize = 15;
const MAX_PIXELS: usize = 8_388_608;
const MAX_FIELDS: usize = 20_000;
const MAX_OBJECTS: usize = 1024;
const MAX_PRIMITIVES: usize = 4096;

#[repr(C)]
struct Slot<const N: usize> {
    tag: [u8; 16],
    data: [u8; N],
}

#[used]
static SCENE_SLOT: Slot<SCENE_CAPACITY> = Slot {
    tag: *b"CBFLARE_SCENE_01",
    data: [0xa5; SCENE_CAPACITY],
};
#[used]
static MANIFEST_SLOT: Slot<MANIFEST_CAPACITY> = Slot {
    tag: *b"CBFLARE_MANIF_01",
    data: [0xb7; MANIFEST_CAPACITY],
};

thread_local! {
    static HOST: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) };
    static CACHE: RefCell<Option<(usize, Scene)>> = const { RefCell::new(None) };
}

fn slot_byte<const N: usize>(slot: &Slot<N>, index: usize) -> Result<u8, ()> {
    if index >= N {
        return Err(());
    }
    // The build tool changes only the audited active data segment after compilation.
    // Volatile reads prevent constant folding of the template placeholder.
    Ok(unsafe { std::ptr::read_volatile(slot.data.as_ptr().add(index)) })
}

fn scene_word(index: usize) -> Result<usize, ()> {
    let mut bytes = [0; 4];
    for (i, byte) in bytes.iter_mut().enumerate() {
        *byte = slot_byte(&SCENE_SLOT, index + i)?;
    }
    Ok(u32::from_le_bytes(bytes) as usize)
}

fn embedded_scene(index: usize) -> Result<Scene, ()> {
    for (i, byte) in b"CBFLIB01".iter().enumerate() {
        if slot_byte(&SCENE_SLOT, i)? != *byte {
            return Err(());
        }
    }
    let length = scene_word(8)?;
    let count = scene_word(12)?;
    if !(1..=256).contains(&count) || index >= count || length > SCENE_CAPACITY {
        return Err(());
    }
    let mut end = 16 + count * 8;
    let mut selected = None;
    for i in 0..count {
        let start = scene_word(16 + i * 8)?;
        let size = scene_word(20 + i * 8)?;
        if start != end || size == 0 || start.checked_add(size).is_none_or(|e| e > length) {
            return Err(());
        }
        if i == index {
            selected = Some((start, size));
        }
        end += size;
    }
    if end != length {
        return Err(());
    }
    let (start, size) = selected.ok_or(())?;
    let mut data = Vec::new();
    data.try_reserve_exact(size).map_err(|_| ())?;
    for i in start..start + size {
        data.push(slot_byte(&SCENE_SLOT, i)?);
    }
    Scene::parse(&data)
}

#[unsafe(no_mangle)]
pub extern "C" fn ec_api_version() -> i32 {
    1
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_ptr() -> i32 {
    (MANIFEST_SLOT.data.as_ptr() as usize + 4) as i32
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_manifest_len() -> i32 {
    let bytes = std::array::from_fn(|i| slot_byte(&MANIFEST_SLOT, i).unwrap_or(0));
    let length = u32::from_le_bytes(bytes) as usize;
    if length <= MANIFEST_CAPACITY - 4 {
        length as i32
    } else {
        0
    }
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_alloc(bytes: i32) -> i32 {
    if bytes <= 0 || bytes as usize > MAX_PIXELS * 16 + FLAT * 8 {
        return 0;
    }
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let len = (bytes as usize).div_ceil(8);
        let extra = len.saturating_sub(host.len());
        if host.try_reserve(extra).is_err() {
            return 0;
        }
        host.resize(len, 0);
        host.as_mut_ptr() as i32
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn ec_render(
    pixels: i32,
    width: i32,
    height: i32,
    params: i32,
    nparams: i32,
    time: f64,
    scale: f64,
) -> i32 {
    if width <= 0 || height <= 0 || nparams != FLAT as i32 {
        return 1;
    }
    let Some(n) = (width as usize)
        .checked_mul(height as usize)
        .filter(|n| *n <= MAX_PIXELS)
    else {
        return 1;
    };
    HOST.with(|host| {
        let mut host = host.borrow_mut();
        let start = host.as_mut_ptr() as usize;
        let end = start + host.len() * 8;
        let pp = params as u32 as usize;
        let xp = pixels as u32 as usize;
        if pp != start || xp != start + FLAT * 8 || xp.checked_add(n * 16).is_none_or(|v| v > end) {
            return 1;
        }
        let p = unsafe { std::slice::from_raw_parts(pp as *const f64, FLAT) };
        let px = unsafe { std::slice::from_raw_parts_mut(xp as *mut [f32; 4], n) };
        if !valid_params(p, time, scale) {
            return 1;
        }
        CACHE.with(|cache| {
            let mut cache = cache.borrow_mut();
            let index = p[0] as usize;
            if cache.as_ref().is_none_or(|(i, _)| *i != index) {
                let Ok(scene) = embedded_scene(index) else {
                    return 2;
                };
                *cache = Some((index, scene));
            }
            let Some((_, scene)) = cache.as_ref() else {
                return 2;
            };
            match render(scene, px, width as usize, height as usize, p, time, scale) {
                Ok(()) => 0,
                Err(()) => 3,
            }
        })
    })
}

#[derive(Clone)]
struct Field {
    id: u32,
    kind: u32,
    raw: [u8; 32],
}
#[derive(Clone)]
struct Fields(Vec<Field>);
impl Fields {
    fn get(&self, id: u32, kind: u32) -> Result<Option<&Field>, ()> {
        let mut fields = self.0.iter().filter(|f| f.id == id && f.kind != 6);
        let Some(field) = fields.next() else {
            return Ok(None);
        };
        if fields.next().is_some() || field.kind != kind {
            return Err(());
        }
        Ok(Some(field))
    }
    fn number(&self, id: u32, default: f64) -> Result<f64, ()> {
        Ok(self.get(id, 0)?.map_or(default, |f| {
            f32::from_le_bytes(f.raw[..4].try_into().unwrap_or([0; 4])) as f64
        }))
    }
    fn integer(&self, id: u32, default: i32) -> Result<i32, ()> {
        Ok(self.get(id, 3)?.map_or(default, |f| {
            i32::from_le_bytes(f.raw[..4].try_into().unwrap_or([0; 4]))
        }))
    }
    fn boolean(&self, id: u32) -> Result<bool, ()> {
        Ok(self.get(id, 4)?.is_some_and(|f| f.raw[0] != 0))
    }
    fn vector(&self, id: u32, default: [f64; 2]) -> Result<[f64; 2], ()> {
        let Some(f) = self.get(id, 1)? else {
            return Ok(default);
        };
        Ok(std::array::from_fn(|i| {
            f32::from_le_bytes(f.raw[i * 4..i * 4 + 4].try_into().unwrap_or([0; 4])) as f64
        }))
    }
    fn color(&self, id: u32, default: [f64; 3]) -> Result<[f64; 3], ()> {
        Ok(self.get(id, 2)?.map_or(default, |f| {
            std::array::from_fn(|i| f.raw[i] as f64 / 255.0)
        }))
    }
}
struct Object {
    kind: u32,
    hidden: bool,
    solo: bool,
    fields: Fields,
}
struct Scene {
    globals: Fields,
    objects: Vec<Object>,
}
struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
    fields: usize,
}
impl Reader<'_> {
    fn atom(&mut self, expected: u16, size: usize) -> Result<&[u8], ()> {
        let head = self
            .data
            .get(self.pos..self.pos.checked_add(4).ok_or(())?)
            .ok_or(())?;
        let tag = u16::from_le_bytes([head[0], head[1]]);
        let length = u16::from_le_bytes([head[2], head[3]]) as usize;
        if tag != expected || length != size {
            return Err(());
        }
        self.pos += 4;
        let data = self
            .data
            .get(self.pos..self.pos.checked_add(size).ok_or(())?)
            .ok_or(())?;
        self.pos += size;
        Ok(data)
    }
    fn marker(&mut self, tag: u16) -> Result<(), ()> {
        if self.atom(tag, 1)? == [0] {
            Ok(())
        } else {
            Err(())
        }
    }
    fn word(&mut self, tag: u16) -> Result<u32, ()> {
        Ok(u32::from_le_bytes(
            self.atom(tag, 4)?.try_into().map_err(|_| ())?,
        ))
    }
    fn block(&mut self, end: u16) -> Result<Fields, ()> {
        let mut fields = Vec::new();
        loop {
            let head = self.data.get(self.pos..self.pos + 2).ok_or(())?;
            if u16::from_le_bytes([head[0], head[1]]) == end {
                self.marker(end)?;
                break;
            }
            let id = self.word(50)?;
            let kind = self.word(51)?;
            let raw: [u8; 32] = self.atom(52, 32)?.try_into().map_err(|_| ())?;
            self.marker(2000)?;
            self.fields += 1;
            if self.fields > MAX_FIELDS || kind > 6 {
                return Err(());
            }
            if kind <= 1 {
                for index in 0..if kind == 0 { 1 } else { 2 } {
                    let value = f32::from_le_bytes(
                        raw[index * 4..index * 4 + 4].try_into().map_err(|_| ())?,
                    );
                    if !value.is_finite() || value.abs() > 1e6 {
                        return Err(());
                    }
                }
            }
            fields.push(Field { id, kind, raw });
        }
        Ok(Fields(fields))
    }
}
impl Scene {
    fn parse(data: &[u8]) -> Result<Self, ()> {
        if data.len() > SCENE_CAPACITY || data.get(..4) != Some(b"OFP\x03") {
            return Err(());
        }
        let mut reader = Reader {
            data,
            pos: 4,
            fields: 0,
        };
        reader.marker(3000)?;
        let globals = reader.block(4000)?;
        let mut objects = Vec::new();
        while reader.pos < data.len() {
            if objects.len() == MAX_OBJECTS {
                return Err(());
            }
            let kind = reader.word(1)?;
            if ![1, 2, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15].contains(&kind) {
                return Err(());
            }
            reader.atom(2, 64)?; // Name bytes retained in embedded data, never opened as a path.
            let hidden = reader.atom(3, 1)?[0];
            let solo = reader.atom(4, 1)?[0];
            if hidden > 1 || solo > 1 {
                return Err(());
            }
            objects.push(Object {
                kind,
                hidden: hidden == 1,
                solo: solo == 1,
                fields: reader.block(1000)?,
            });
        }
        Ok(Self { globals, objects })
    }
}

fn valid_params(p: &[f64], time: f64, scale: f64) -> bool {
    p.len() == FLAT
        && p.iter().all(|v| v.is_finite() && v.abs() <= 1e9)
        && p[0] >= 0.0
        && p[0] < 256.0
        && p[0] == p[0].floor()
        && (0.0..=100000.0).contains(&p[5])
        && (0.0..=10000.0).contains(&p[6])
        && p[8..12].iter().all(|v| (0.0..=1.0).contains(v))
        && [0.0, 1.0].contains(&p[12])
        && [0.0, 1.0, 2.0].contains(&p[14])
        && time.is_finite()
        && time.abs() <= 1e9
        && scale.is_finite()
        && (0.0..=16.0).contains(&scale)
        && scale > 0.0
}

// Original repeatable integer hash, independent of vendor PRNG/texture code.
fn noise(seed: f64, stream: u64) -> f64 {
    let mut x = seed
        .to_bits()
        .wrapping_add(stream.wrapping_mul(0xd1342543de82ef95));
    x ^= x >> 29;
    x = x.wrapping_mul(0x9e3779b185ebca87);
    x ^= x >> 32;
    (x >> 11) as f64 / (1_u64 << 53) as f64
}
#[derive(Clone)]
struct Primitive {
    kind: u32,
    center: [f64; 2],
    radius: [f64; 2],
    orientation: [f64; 2],
    color: [f64; 3],
    power: f64,
    detail: f64,
    gamma: f64,
    thickness: f64,
    sides: f64,
    shape: i32,
    completion: f64,
    phase: f64,
}

fn prepare(scene: &Scene, w: usize, h: usize, p: &[f64], time: f64) -> Result<Vec<Primitive>, ()> {
    let g = &scene.globals;
    let global_scale = g.number(0x70, 100.0)? / 100.0 * p[6] / 100.0;
    let global_aspect = g.number(8, 1.0)?.abs().max(1e-6);
    let global_color = g.color(4, [1.0; 3])?;
    let mut primitives = Vec::new();
    let solo = scene.objects.iter().any(|o| o.solo && !o.hidden);
    let light = [p[1], p[2]];
    let axis = [p[3] - p[1], p[4] - p[2]];
    for (order, object) in scene.objects.iter().enumerate() {
        if object.hidden || (solo && !object.solo) {
            continue;
        }
        let f = &object.fields;
        let shape = f.integer(0x0b, 1)?;
        if [4, 14, 15].contains(&object.kind) && shape == 2 {
            continue;
        } // Missing texture: omit, never replace with a circle.
        if [4, 14, 15].contains(&object.kind) && ![0, 1].contains(&shape) {
            return Err(());
        }
        let base_scale = f.number(1, 100.0)?.max(0.0) / 100.0;
        let scale = if f.boolean(0x1b)? {
            p[6] / 100.0
        } else {
            global_scale
        };
        let stretch = f.vector(0x55, [100.0; 2])?;
        let aspect = f.number(8, 1.0)?.abs().max(1e-6) * global_aspect;
        let offset = f.vector(3, [0.0; 2])?;
        let distance = if object.kind == 7 {
            [f.number(0x67, 0.0)?, 0.0]
        } else {
            f.vector(2, [0.0; 2])?
        };
        let translation = f.integer(6, 0)?;
        let custom = f.vector(0x17, [0.0; 2])?;
        let position = [
            light[0] + (axis[0] * distance[0] - axis[1] * distance[1]) / 100.0,
            light[1] + (axis[1] * distance[0] + axis[0] * distance[1]) / 100.0,
        ];
        let mut center = [
            position[0] + offset[0] * w as f64 / 100.0,
            position[1] + offset[1] * h as f64 / 100.0,
        ];
        match translation {
            0 => {}
            1 => center[1] = p[4] + offset[1] * h as f64 / 100.0,
            2 => center[0] = p[3] + offset[0] * w as f64 / 100.0,
            3 => {
                center = [
                    p[3] + offset[0] * w as f64 / 100.0,
                    p[4] + offset[1] * h as f64 / 100.0,
                ]
            }
            4 => {
                center = [
                    (custom[0] + offset[0]) * w as f64 / 100.0,
                    (custom[1] + offset[1]) * h as f64 / 100.0,
                ]
            }
            _ => return Err(()),
        }
        let mut angle = f.number(5, 0.0)?.to_radians();
        if !f.boolean(0x16)? {
            angle += p[7].to_radians();
        }
        match f.integer(0x29, 0)? {
            0 => {}
            1 => angle += (light[1] - center[1]).atan2(light[0] - center[0]),
            2 => angle += (p[4] - center[1]).atan2(p[3] - center[0]),
            _ => return Err(()),
        }
        let power = f.number(0, 100.0)?.max(0.0) / 100.0
            * if f.boolean(0x1a)? { 1.0 } else { p[5] / 100.0 };
        let color_source = f.integer(7, 0)?;
        let mut color = match color_source {
            0 => global_color,
            1 | 3 => f.color(4, global_color)?,
            2 => spectrum((order as f64 * 0.61803398875).fract()),
            _ => return Err(()),
        };
        if p[12] == 0.0 {
            let luma = color[0] * 0.2126 + color[1] * 0.7152 + color[2] * 0.0722;
            for (i, c) in color.iter_mut().enumerate() {
                *c = luma * p[8 + i];
            }
        } else {
            for (i, c) in color.iter_mut().enumerate() {
                *c *= p[8 + i];
            }
        }
        let count = if [4, 14].contains(&object.kind) {
            f.number(0x0e, 1.0)?.round()
        } else {
            1.0
        };
        if !(0.0..=128.0).contains(&count) || primitives.len() + count as usize > MAX_PRIMITIVES {
            return Err(());
        }
        let seed = f.number(0x12, 0.0)? + g.number(0x12, 0.0)?;
        let phase = p[13].to_radians()
            + if f.boolean(0x6e)? {
                time * f.number(0x6c, 0.0)?
            } else {
                0.0
            };
        let radius = 0.5 * w.min(h) as f64 * base_scale * scale;
        for index in 0..count as usize {
            let mut c = center;
            if object.kind == 4 {
                let spread = f.number(0x0d, 0.0)? / 100.0;
                let t = if count <= 1.0 {
                    0.0
                } else {
                    index as f64 / (count - 1.0) - 0.5
                };
                c[0] += axis[0] * spread * t;
                c[1] += axis[1] * spread * t;
            } else if object.kind == 14 {
                let a = noise(seed, index as u64 * 3) * TAU;
                let r = noise(seed, index as u64 * 3 + 1).sqrt() * f.number(0x3f, 100.0)? / 100.0
                    * w.min(h) as f64;
                c[0] += a.cos() * r;
                c[1] += a.sin() * r;
            }
            let random_scale = (1.0
                + (noise(seed, index as u64 * 3 + 2) * 2.0 - 1.0) * f.number(0x0f, 0.0)? / 100.0)
                .max(0.0);
            let primitive = Primitive {
                kind: object.kind,
                center: c,
                radius: [
                    radius * stretch[0].abs() / 100.0 * aspect * random_scale,
                    radius * stretch[1].abs() / 100.0 / aspect * random_scale,
                ],
                orientation: [angle.sin(), angle.cos()],
                color,
                power,
                detail: f.number(0x34, 6.0)?.abs().max(1.0),
                gamma: f.number(0x1d, 1.0)?.abs().max(0.01),
                thickness: if object.kind == 2 || object.kind == 9 {
                    f.number(0x43, 5.0)?.abs() / 100.0
                } else {
                    f.number(0x38, 10.0)?.abs() / 100.0
                },
                sides: f.number(0x0c, 6.0)?.round().clamp(3.0, 64.0),
                shape,
                completion: f.number(0x31, 100.0)?.clamp(0.0, 100.0) / 100.0,
                phase,
            };
            if !primitive
                .radius
                .iter()
                .chain(primitive.center.iter())
                .all(|v| v.is_finite() && v.abs() <= 1e12)
            {
                return Err(());
            }
            primitives.push(primitive);
        }
    }
    Ok(primitives)
}

fn spectrum(t: f64) -> [f64; 3] {
    std::array::from_fn(|i| {
        (1.0 - (t * 6.0 - i as f64 * 2.0)
            .rem_euclid(6.0)
            .min(6.0 - (t * 6.0 - i as f64 * 2.0).rem_euclid(6.0)))
        .clamp(0.0, 1.0)
    })
}
fn sample(o: &Primitive, x: f64, y: f64) -> f64 {
    let dx = x - o.center[0];
    let dy = y - o.center[1];
    let [s, c] = o.orientation;
    let u = (dx * c + dy * s) / o.radius[0].max(1e-9);
    let v = (-dx * s + dy * c) / o.radius[1].max(1e-9);
    let r2 = u * u + v * v;
    let r = r2.sqrt();
    let needs_angle = o.completion < 1.0
        || [5, 7, 8, 9, 11, 12].contains(&o.kind)
        || ([4, 14, 15].contains(&o.kind) && o.shape == 0);
    let theta = if needs_angle { v.atan2(u) } else { 0.0 };
    if o.completion < 1.0 && (theta + PI).rem_euclid(TAU) / TAU > o.completion {
        return 0.0;
    }
    match o.kind {
        1 => (-if o.gamma == 1.0 {
            r2
        } else {
            r2.powf(1.0 / o.gamma)
        })
        .exp(),
        2 => (-u.abs()).exp() * (-v.abs() / o.thickness.max(0.005)).exp(),
        4 | 14 | 15 => {
            let boundary = if o.shape == 0 {
                (PI / o.sides).cos()
                    / ((theta + PI / o.sides).rem_euclid(TAU / o.sides) - PI / o.sides).cos()
            } else {
                1.0
            };
            ((boundary - r) / 0.05 + 0.5).clamp(0.0, 1.0)
        }
        5 => (-r * 2.0).exp() * (0.15 + 0.85 * (theta * o.detail + o.phase).cos().powi(24)),
        6 => (-((r - 1.0) / o.thickness.max(0.005)).powi(2)).exp(),
        7 => {
            (-((r - 1.0) / o.thickness.max(0.005)).powi(2)).exp()
                * (0.2 + 0.8 * (theta * o.detail + o.phase).sin().abs())
        }
        8 => (-r * 3.0).exp() * (theta * 2.0 + o.phase).cos().powi(32),
        9 => (-r * 2.0).exp() * (theta * o.detail + o.phase).cos().powi(24),
        11 => (-r * 1.5).exp() * (0.05 + 0.95 * (theta * o.detail + o.phase).cos().powi(24)),
        12 => {
            let edge = 1.0 + 0.1 * (theta * o.detail + o.phase).sin();
            (-((r - edge) / o.thickness.max(0.005)).powi(2)).exp()
        }
        _ => 0.0,
    }
}

fn render(
    scene: &Scene,
    pixels: &mut [[f32; 4]],
    w: usize,
    h: usize,
    p: &[f64],
    time: f64,
    scale: f64,
) -> Result<(), ()> {
    if w == 0
        || h == 0
        || w.checked_mul(h) != Some(pixels.len())
        || pixels.len() > MAX_PIXELS
        || !valid_params(p, time, scale)
        || pixels
            .iter()
            .flatten()
            .any(|v| !v.is_finite() || v.abs() > 1e6)
    {
        return Err(());
    }
    let blend = scene.globals.integer(9, 0)?;
    if ![0, 1].contains(&blend) {
        return Err(());
    }
    let objects = prepare(scene, w, h, p, time)?;
    let mut light = Vec::new();
    light.try_reserve_exact(pixels.len()).map_err(|_| ())?;
    light.resize(pixels.len(), [0.0_f64; 3]);
    for object in objects {
        if object.radius[0] <= 1e-9 || object.radius[1] <= 1e-9 || object.power == 0.0 {
            continue;
        }
        let extent = object.radius[0].max(object.radius[1])
            * if [4, 14, 15].contains(&object.kind) {
                1.1
            } else {
                8.0
            };
        let x0 = (object.center[0] - extent).floor().clamp(0.0, w as f64) as usize;
        let x1 = (object.center[0] + extent + 1.0)
            .ceil()
            .clamp(0.0, w as f64) as usize;
        let y0 = (object.center[1] - extent).floor().clamp(0.0, h as f64) as usize;
        let y1 = (object.center[1] + extent + 1.0)
            .ceil()
            .clamp(0.0, h as f64) as usize;
        for y in y0..y1 {
            for x in x0..x1 {
                let intensity = sample(&object, x as f64, y as f64) * object.power;
                let pixel = &mut light[y * w + x];
                for (i, c) in pixel.iter_mut().enumerate() {
                    let value = intensity * object.color[i];
                    *c = if blend == 0 {
                        (*c + value).min(1e6)
                    } else {
                        1.0 - (1.0 - (*c).clamp(0.0, 1.0)) * (1.0 - value.clamp(0.0, 1.0))
                    };
                }
            }
        }
    }
    for (pixel, light) in pixels.iter_mut().zip(light) {
        let alpha = light
            .iter()
            .copied()
            .fold(0.0_f64, f64::max)
            .clamp(0.0, 1.0)
            * p[11];
        let source = *pixel;
        for i in 0..3 {
            pixel[i] = (light[i] * p[11] + if p[14] == 2.0 { source[i] as f64 } else { 0.0 })
                .clamp(-1e6, 1e6) as f32;
        }
        pixel[3] = if p[14] == 0.0 {
            1.0
        } else if p[14] == 1.0 {
            alpha as f32
        } else {
            (alpha + source[3] as f64 * (1.0 - alpha)).clamp(0.0, 1.0) as f32
        };
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn number(id: u32, v: f32) -> Field {
        let mut raw = [0; 32];
        raw[..4].copy_from_slice(&v.to_le_bytes());
        Field { id, kind: 0, raw }
    }
    fn object(kind: u32) -> Object {
        Object {
            kind,
            hidden: false,
            solo: false,
            fields: Fields(vec![number(0, 100.0), number(1, 20.0)]),
        }
    }
    fn scene() -> Scene {
        Scene {
            globals: Fields(vec![]),
            objects: vec![object(1)],
        }
    }
    fn params() -> [f64; FLAT] {
        [
            0.0, 16.0, 16.0, 16.0, 16.0, 100.0, 100.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0,
        ]
    }
    #[test]
    fn glow_is_symmetric_colored_and_deterministic() {
        let mut p = params();
        p[8] = 0.5;
        p[9] = 0.25;
        let mut px = vec![[0.0; 4]; 33 * 33];
        render(&scene(), &mut px, 33, 33, &p, 0.0, 1.0).unwrap();
        assert_eq!(px[16 * 33 + 16], [0.5, 0.25, 1.0, 1.0]);
        assert_eq!(px[16 * 33 + 15], px[15 * 33 + 16]);
        assert!(px[16 * 33 + 15][0] > px[16 * 33 + 5][0]);
        let mut again = vec![[0.0; 4]; 33 * 33];
        render(&scene(), &mut again, 33, 33, &p, 0.0, 1.0).unwrap();
        assert_eq!(px, again);
    }
    #[test]
    fn object_visibility_and_solo_are_honored() {
        let mut s = scene();
        s.objects[0].hidden = true;
        let mut px = vec![[0.0; 4]; 33 * 33];
        render(&s, &mut px, 33, 33, &params(), 0.0, 1.0).unwrap();
        assert!(px.iter().all(|p| *p == [0.0; 4]));
        s.objects.push(object(6));
        s.objects[1].solo = true;
        s.objects[0].hidden = false;
        render(&s, &mut px, 33, 33, &params(), 0.0, 1.0).unwrap();
        assert!(px[16 * 33 + 16][0] < 1e-10);
    }
    #[test]
    fn all_procedural_families_have_distinct_finite_profiles() {
        let mut outputs = Vec::new();
        for kind in [1, 2, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15] {
            let s = Scene {
                globals: Fields(vec![]),
                objects: vec![object(kind)],
            };
            let mut px = vec![[0.0; 4]; 33 * 33];
            render(&s, &mut px, 33, 33, &params(), 0.1, 1.0).unwrap();
            assert!(px.iter().flatten().all(|v| v.is_finite()));
            assert!(px.iter().any(|p| p[0] > 0.0));
            outputs.push(px);
        }
        assert_ne!(outputs[0], outputs[1]);
        assert_ne!(outputs[4], outputs[5]);
        assert_ne!(outputs[6], outputs[7]);
    }
    #[test]
    fn errors_do_not_modify_input_and_modes_preserve_source() {
        let mut p = params();
        let original = vec![[0.1, 0.2, 0.3, 0.5]; 33 * 33];
        let mut px = original.clone();
        p[5] = f64::NAN;
        assert!(render(&scene(), &mut px, 33, 33, &p, 0.0, 1.0).is_err());
        assert_eq!(px, original);
        p = params();
        p[5] = 0.0;
        p[14] = 2.0;
        render(&scene(), &mut px, 33, 33, &p, 0.0, 1.0).unwrap();
        assert_eq!(px, original);
        p[14] = 0.0;
        render(&scene(), &mut px, 33, 33, &p, 0.0, 1.0).unwrap();
        assert!(px.iter().all(|p| *p == [0.0, 0.0, 0.0, 1.0]));
    }
    #[test]
    fn malformed_or_unknown_ofp_never_uses_a_default_scene() {
        assert!(Scene::parse(b"OFP\x04").is_err());
        assert!(Scene::parse(b"OFP\x03").is_err());
        assert!(embedded_scene(0).is_err());
        let mut p = params();
        p[0] = 0.5;
        assert!(!valid_params(&p, 0.0, 1.0));
    }
}
