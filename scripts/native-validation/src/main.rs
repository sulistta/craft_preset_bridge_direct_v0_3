use std::io::{BufRead, Write};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("layer-render") {
        // Original synthetic inputs through the official native effect/host API.
        // This validates Layer routing separately from opaque Adobe references.
        struct Host {
            inputs: std::collections::HashMap<u64, effectcraft_effects::LayerPixels>,
            requested: std::sync::Mutex<Vec<u64>>,
        }
        impl effectcraft_effects::EffectHost for Host {
            fn layer(&self, id: u64, _: bool) -> Option<effectcraft_effects::LayerPixels> {
                self.requested.lock().unwrap().push(id);
                self.inputs.get(&id).cloned()
            }
            fn audio(&self, _: u64, _: f64, _: usize, _: u32) -> Option<Vec<f32>> { None }
        }
        fn image(v: &serde_json::Value) -> effectcraft_effects::Image {
            let w = v["width"].as_u64().unwrap();
            let h = v["height"].as_u64().unwrap();
            assert!((1..=65536).contains(&w) && (1..=65536).contains(&h) && w * h <= 8_388_608);
            let mut image = effectcraft_effects::Image::new(w as u32, h as u32);
            image.data = serde_json::from_value(v["pixels"].clone()).unwrap();
            assert_eq!(image.data.len(), (w * h) as usize);
            assert!(image.data.iter().flatten().all(|v| v.is_finite()));
            image
        }
        let input: serde_json::Value = serde_json::from_slice(&std::fs::read(&args[2]).unwrap()).unwrap();
        let spec = effectcraft_effects::find(input["effect"].as_str().unwrap()).unwrap();
        let mut params = effectcraft_effects::Params { values: spec.params.iter().map(|p| (p.id.to_string(), p.default.clone())).collect() };
        for (id, value) in input["params"].as_object().unwrap() {
            let p = spec.params.iter().find(|p| p.id == id).unwrap();
            params.values.insert(id.clone(), p.default.coerce_json(value).unwrap());
        }
        let inputs = input["inputs"].as_array().unwrap();
        assert!(inputs.len() <= 4);
        let mut host = Host { inputs: Default::default(), requested: Default::default() };
        let mut total = 0;
        for item in inputs {
            let uid = item["uid"].as_u64().filter(|uid| *uid > 0).unwrap();
            let image = image(item);
            total += image.data.len(); assert!(total <= 8_388_608);
            let size = [image.width as f64, image.height as f64];
            assert!(host.inputs.insert(uid, effectcraft_effects::LayerPixels {
                buf: effectcraft_effects::Buf { img: image, offset: [0.0,0.0], scale: 1.0 }, size,
            }).is_none());
        }
        let img = image(&input);
        let size = [img.width as f64, img.height as f64];
        let ctx = effectcraft_effects::EffectCtx { params: &params, time: 0.0, layer_size: size,
            seed: 1, adjustment: false, env: effectcraft_effects::EffectEnv { host: Some(&host), ..Default::default() } };
        let output = (spec.render)(&ctx, effectcraft_effects::Buf {img, offset:[0.0,0.0],scale:1.0});
        assert!(output.img.data.iter().flatten().all(|v|v.is_finite()));
        println!("{}", serde_json::json!({"pixels":output.img.data,"requested_layer_uids":*host.requested.lock().unwrap()}));
        return;
    }
    if args.get(1).map(String::as_str) == Some("plugin-render") {
        let spec = effectcraft_plugin::load_wasm(&std::fs::read(&args[2]).unwrap(), &args[2]).unwrap();
        let input: serde_json::Value = serde_json::from_slice(&std::fs::read(&args[3]).unwrap()).unwrap();
        let mut params = effectcraft_effects::Params { values: spec.params.iter().map(|p| (p.id.to_string(), p.default.clone())).collect() };
        for (id, value) in input["params"].as_object().unwrap() {
            let p = spec.params.iter().find(|p| p.id == id).unwrap();
            params.values.insert(id.clone(), p.default.coerce_json(value).unwrap());
        }
        let mut pixels: Vec<[f32; 4]> = if let Some(pixel) = input.get("fill") {
            let w = input["width"].as_u64().unwrap() as usize;
            let h = input["height"].as_u64().unwrap() as usize;
            assert!(w * h <= 8_388_608);
            vec![serde_json::from_value(pixel.clone()).unwrap(); w * h]
        } else { serde_json::from_value(input["pixels"].clone()).unwrap() };
        if let Some(replacements) = input.get("replace").and_then(|v| v.as_array()) {
            for replacement in replacements {
                let index = replacement["index"].as_u64().unwrap() as usize;
                assert!(index < pixels.len());
                pixels[index] = serde_json::from_value(replacement["pixel"].clone()).unwrap();
            }
        }
        // Original synthetic checker pixels for nonuniform full-frame renderer audits.
        if let Some(checker) = input.get("checker") {
            let width = input["width"].as_u64().unwrap() as usize;
            let cell = checker["cell"].as_u64().unwrap() as usize;
            assert!(width > 0 && (1..=65536).contains(&cell));
            let first: [f32; 4] = serde_json::from_value(checker["first"].clone()).unwrap();
            let second: [f32; 4] = serde_json::from_value(checker["second"].clone()).unwrap();
            for (i, pixel) in pixels.iter_mut().enumerate() {
                *pixel = if ((i % width) / cell + (i / width) / cell).is_multiple_of(2) { first } else { second };
            }
        }
        let width = input["width"].as_u64().unwrap_or(pixels.len() as u64) as u32;
        let height = input["height"].as_u64().unwrap_or(1) as u32;
        assert_eq!(width as usize * height as usize, pixels.len());
        let time = input["time"].as_f64().unwrap_or(0.0);
        let mut img = effectcraft_effects::Image::new(width, height);
        img.data = pixels;
        let ctx = effectcraft_effects::EffectCtx { params: &params, time, layer_size: [width as f64, height as f64], seed: 1, adjustment: false, env: Default::default() };
        let mut buf = effectcraft_effects::Buf { img, offset: [0.0, 0.0], scale: input["scale"].as_f64().unwrap_or(1.0) };
        if input["strict_render"].as_bool().unwrap_or(false) {
            let plugin = effectcraft_effects::plugin::plugin(spec.id).unwrap();
            let flat = effectcraft_effects::plugin::flatten(plugin.manifest(), &ctx, &buf);
            let p = effectcraft_plugin::PluginParams { manifest: plugin.manifest(), flat: &flat };
            let mut frame = effectcraft_plugin::PluginFrame { width, height, pixels: &mut buf.img.data, scale: buf.scale };
            // Surface traps/errors instead of accepting the wrapper's unchanged-frame fallback.
            plugin.render(&mut frame, &p, time).unwrap();
        } else { buf = (spec.render)(&ctx, buf); }
        if input["summary"].as_bool().unwrap_or(false) {
            assert!(buf.img.data.iter().flatten().all(|v| v.is_finite()));
            println!("{}", serde_json::json!({"pixels": buf.img.data.len(), "center": buf.img.data[(height / 2 * width + width / 2) as usize], "sum_rgb": buf.img.data.iter().map(|p| p[0] as f64 + p[1] as f64 + p[2] as f64).sum::<f64>()}));
        } else { println!("{}", serde_json::to_string(&buf.img.data).unwrap()); }
        return;
    }
    if args.get(1).map(String::as_str) == Some("curve-eval") {
        let data: Vec<serde_json::Value> = serde_json::from_slice(&std::fs::read(&args[2]).unwrap()).unwrap();
        let evaluated: Vec<serde_json::Value> = data.iter().map(|entry| {
            let curve = effectcraft_effects::Curve::parse(entry["points"].as_str().unwrap());
            let values: Vec<f32> = entry["inputs"].as_array().unwrap().iter().map(|x| {
                let x = x.as_f64().unwrap() as f32;
                curve.as_ref().map(|c| c.eval(x)).unwrap_or(x)
            }).collect();
            let mut output = serde_json::json!({"id": entry["id"], "values": values});
            if let Some(channel) = entry["channel"].as_str() {
                let spec = effectcraft_effects::find("ec.color.curves").unwrap();
                let mut params = effectcraft_effects::Params {
                    values: spec.params.iter().map(|p| (p.id.to_string(), p.default.clone())).collect()
                };
                let param = spec.params.iter().find(|p| p.id == channel).unwrap();
                params.values.insert(channel.to_string(), param.default.coerce_json(&entry["points"]).unwrap());
                let inputs = entry["inputs"].as_array().unwrap();
                let mut img = effectcraft_effects::Image::new(inputs.len() as u32, 1);
                for (pixel, value) in img.data.iter_mut().zip(inputs.iter()) {
                    let v = value.as_f64().unwrap() as f32;
                    *pixel = if channel == "alpha" { [0.5*v, 0.5*v, 0.5*v, v] } else { [v,v,v,1.0] };
                }
                let ctx = effectcraft_effects::EffectCtx {
                    params: &params, time: 0.0, layer_size: [inputs.len() as f64, 1.0],
                    seed: 1, adjustment: false, env: Default::default()
                };
                let rendered = (spec.render)(&ctx, effectcraft_effects::Buf {img, offset:[0.0,0.0],scale:1.0});
                let component = match channel { "green" => 1, "blue" => 2, "alpha" => 3, _ => 0 };
                output["rendered_values"] = serde_json::json!(rendered.img.data.iter().map(|p| p[component]).collect::<Vec<_>>());
            }
            output
        }).collect();
        println!("{}", serde_json::to_string(&evaluated).unwrap());
        return;
    }
    if args.get(1).map(String::as_str) == Some("catalog-filmcraft") {
        println!("{}", serde_json::to_string_pretty(filmcraft_project::effect::effect_defs()).unwrap());
        return;
    }
    if args.get(1).map(String::as_str) == Some("catalog-effectcraft") {
        let effects: Vec<serde_json::Value> = effectcraft_effects::all().into_iter().map(|e| {
            serde_json::json!({"id": e.id, "name": e.name, "category": e.category,
                "params": e.params.iter().map(|p| serde_json::json!({
                    "id": p.id, "name": p.name, "default": p.default.to_json(), "ui": p.ui
                })).collect::<Vec<_>>()})
        }).collect();
        println!("{}", serde_json::to_string_pretty(&effects).unwrap());
        return;
    }
    if args.get(1).map(String::as_str) == Some("filmcraft") {
        let data: serde_json::Value = serde_json::from_slice(&std::fs::read(&args[2]).unwrap()).unwrap();
        assert_eq!(data["format"], "filmcraft.effect-presets");
        for preset in data["presets"].as_array().unwrap() {
            for effect in preset["effects"].as_array().unwrap() {
                let instance: filmcraft_project::EffectInstance = serde_json::from_value(effect.clone()).unwrap();
                let spec = instance.def().expect("official effect registry");
                for name in instance.params.keys() { assert!(spec.param(name).is_some()); }
            }
        }
        let mut session = filmcraft_engine::Session::new(std::sync::Arc::new(filmcraft_engine::FsServices));
        let imported = session.execute("presets.import", serde_json::json!({"path":args[2]})).unwrap();
        for preset in data["presets"].as_array().unwrap() {
            let expected: filmcraft_engine::presets::EffectPreset = serde_json::from_value(preset.clone()).unwrap();
            let actual = session.presets.find(&expected.name).expect("imported preset readback");
            assert_eq!(actual, expected, "native import must preserve effects, parameters and timing");
        }
        println!("Official FilmCraft EffectInstance, registry, presets.import and full value readback: {}", imported);
        return;
    }
    let port = args.get(2).map(String::as_str).unwrap_or("19877");
    let listener = std::net::TcpListener::bind(format!("127.0.0.1:{port}")).unwrap();
    let mut session = effectcraft_engine::Session::new();
    session.plugin_loader = Some(effectcraft_plugin::loader);
    session.execute("comp.new", serde_json::json!({"name":"Bridge validation", "frameRate":30,"duration":20})).unwrap();
    session.execute("layer.newSolid", serde_json::json!({"name":"Bridge target"})).unwrap();
    println!("Native EffectCraft engine ready: {port}");
    std::io::stdout().flush().unwrap();
    for socket in listener.incoming() {
        let mut socket = socket.unwrap();
        let reader = std::io::BufReader::new(socket.try_clone().unwrap());
        for line in reader.lines() {
            let Ok(line) = line else {break};
            let request: serde_json::Value = serde_json::from_str(&line).unwrap();
            let params = &request["params"];
            let result = session.execute(params["command"].as_str().unwrap(), params["params"].clone());
            let reply = match result {
                Ok(result) => serde_json::json!({"id":request["id"],"ok":true,"result":result}),
                Err(error) => serde_json::json!({"id":request["id"],"ok":false,"error":error.to_string()}),
            };
            if writeln!(socket, "{}", reply).is_err() {break}
        }
    }
}
