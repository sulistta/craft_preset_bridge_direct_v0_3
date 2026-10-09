//! Original multi-layer engine probe; its images and effect are synthetic.
use effectcraft_engine::Session;
use effectcraft_render::RenderOpts;
use effectcraft_time::Tick;
use serde_json::json;

fn serve() {
    use std::io::{BufRead, Write};
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let mut session = Session::new();
    session.plugin_loader = Some(effectcraft_plugin::loader);
    println!(
        "Bridge experimental host ready: {}",
        listener.local_addr().unwrap().port()
    );
    std::io::stdout().flush().unwrap();
    for socket in listener.incoming() {
        let mut socket = socket.unwrap();
        let reader = std::io::BufReader::new(socket.try_clone().unwrap());
        for line in reader.lines() {
            let Ok(line) = line else { break };
            let request: serde_json::Value = serde_json::from_str(&line).unwrap();
            let command = request["params"]["command"].as_str().unwrap();
            let params = request["params"]["params"].clone();
            // This helper exists only in the disposable probe, not command.list.
            let result: Result<serde_json::Value, String> = if command == "bridge.probe.render" {
                (|| {
                    let cid = session
                        .resolve_comp(params.get("comp"))
                        .map_err(|e| e.to_string())?;
                    let comp = session.project.comp(cid).ok_or("missing comp")?;
                    if comp.width > 64 || comp.height > 64 {
                        return Err("probe images must be at most 64 by 64".into());
                    }
                    let time = params["time"].as_f64().unwrap_or(0.0);
                    let scale = params["scale"].as_f64().unwrap_or(1.0);
                    if !time.is_finite() || time.abs() > 10.0 || (scale != 1.0 && scale != 0.5) {
                        return Err("invalid probe time/scale".into());
                    }
                    let image = session.render(
                        cid,
                        Tick::from_seconds_f64(time),
                        RenderOpts {
                            scale,
                            ..Default::default()
                        },
                    );
                    if image.data.iter().flatten().any(|v| !v.is_finite()) {
                        return Err("nonfinite probe output".into());
                    }
                    Ok(json!({"width":image.width,"height":image.height,"pixels":image.data}))
                })()
            } else {
                session.execute(command, params).map_err(|e| e.to_string())
            };
            let reply = match result {
                Ok(result) => json!({"id":request["id"],"ok":true,"result":result}),
                Err(error) => json!({"id":request["id"],"ok":false,"error":error}),
            };
            if writeln!(socket, "{reply}").is_err() {
                break;
            }
        }
    }
}

fn main() {
    if std::env::args().nth(1).as_deref() == Some("--serve") {
        serve();
        return;
    }
    let out = std::path::PathBuf::from(std::env::args().nth(1).expect("new audit directory"));
    assert!(!out.exists(), "use a new audit directory");
    std::fs::create_dir_all(&out).unwrap();
    let manifest = r#"{"api":2,"id":"org.craftbridge.test.engine.copy","name":"Bridge resource probe","category":"Bridge test","version":"0.1.0","params":[{"id":"source","name":"Source","type":"layer","default":null}]}"#;
    let escaped = manifest.replace('"', "\\\"");
    let module = format!(
        r#"(module
      (memory (export "memory") 2)
      (data (i32.const 16) "{escaped}")
      (func (export "ec_api_version") (result i32) i32.const 2)
      (func (export "ec_manifest_ptr") (result i32) i32.const 16)
      (func (export "ec_manifest_len") (result i32) i32.const {len})
      (func (export "ec_alloc") (param i32) (result i32) i32.const 65536)
      (func (export "ec_render_v2") (param $px i32) (param $w i32) (param $h i32)
        (param $params i32) (param $np i32) (param $time f64) (param $scale f64)
        (param $table i32) (param $nt i32) (result i32)
        local.get $table i32.load offset=92 i32.const 2 i32.ne if i32.const 1 return end
        local.get $table i32.load offset=100 local.get $w i32.ne if i32.const 2 return end
        local.get $table i32.load offset=104 local.get $h i32.ne if i32.const 3 return end
        local.get $px local.get $table i32.load offset=96
        local.get $w local.get $h i32.mul i32.const 16 i32.mul memory.copy
        i32.const 0))"#,
        len = manifest.len()
    );
    let module_path = out.join("original-copy.wat");
    std::fs::write(&module_path, module).unwrap();
    let mut s = Session::new();
    s.plugin_loader = Some(effectcraft_plugin::loader);
    let loaded = s
        .execute("effect.plugins.load", json!({"path": module_path}))
        .unwrap();
    assert_eq!(loaded["loaded"][0]["api"], 2);
    let capabilities = s.execute("effect.plugins.list", json!({})).unwrap();
    assert_eq!(capabilities["apis"], json!([1, 2, 3, 4]));
    assert_eq!(capabilities["bridge_host"]["layer_inputs"], 4);
    let comp = s
        .execute(
            "comp.new",
            json!({"name":"Two inputs", "width":8, "height":4, "duration":2, "frameRate":30}),
        )
        .unwrap();
    let source = s
        .execute(
            "layer.newSolid",
            json!({"name":"Green resource", "color":"#00ff00"}),
        )
        .unwrap()["layer"]
        .as_u64()
        .unwrap();
    let target = s
        .execute(
            "layer.newSolid",
            json!({"name":"Red target", "color":"#ff0000"}),
        )
        .unwrap()["layer"]
        .as_u64()
        .unwrap();
    let cid = s.active_comp_id().unwrap();
    let before = s.render(cid, Tick::ZERO, RenderOpts::default());
    assert_eq!(before.get(2, 1), [1.0, 0.0, 0.0, 1.0]);
    let applied = s
        .execute(
            "effect.apply",
            json!({"effect":"org.craftbridge.test.engine.copy", "layers":[target]}),
        )
        .unwrap();
    let effect_path = applied["paths"][0].as_str().unwrap();
    let path = format!("{effect_path}/source");
    s.execute(
        "prop.set",
        json!({"layer":target, "path":path, "value":source}),
    )
    .unwrap();
    let readback = s
        .execute("prop.get", json!({"layer":target, "path":path}))
        .unwrap();
    assert_eq!(readback["type"], "layer");
    assert_eq!(readback["value"], source);
    let full = s.render(cid, Tick::ZERO, RenderOpts::default());
    assert_eq!((full.width, full.height), (8, 4));
    assert!(full.data.iter().all(|p| *p == [0.0, 1.0, 0.0, 1.0]));
    let half = s.render(
        cid,
        Tick::ZERO,
        RenderOpts {
            scale: 0.5,
            ..Default::default()
        },
    );
    assert_eq!((half.width, half.height), (4, 2));
    assert!(half.data.iter().all(|p| *p == [0.0, 1.0, 0.0, 1.0]));
    let project = out.join("original-two-inputs.ecproj");
    s.execute("file.saveAs", json!({"path":project})).unwrap();
    s.execute("file.open", json!({"path":project})).unwrap();
    let reopened = s
        .execute("prop.get", json!({"layer":target, "path":path}))
        .unwrap();
    assert_eq!(reopened["value"], source);
    let rendered = s.render(
        s.active_comp_id().unwrap(),
        Tick::ZERO,
        RenderOpts::default(),
    );
    assert_eq!(rendered, full);
    // Legacy shipped renderers must still load into this experimental host.
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../src/craft_bridge/extensions");
    let mut legacy = Vec::new();
    for name in [
        "glow",
        "shake",
        "stretch",
        "diffusion",
        "modulation",
        "glint",
        "pixelsort",
        "flicker",
        "median",
        "directional",
        "sharpen",
        "colorize",
    ] {
        let path = root.join(name).join(format!("bridge_{name}.wasm"));
        let result =
            effectcraft_plugin::loader(&std::fs::read(&path).unwrap(), &path.display().to_string())
                .unwrap();
        assert_eq!(result["api"], 1);
        legacy.push(result);
    }
    let audit = json!({"official_upstream_abi":false,"upstream_commit":"e38a92e792c07f1c57c5dcfcab37d91932b9e2b8",
        "host_revision":3, "capabilities":capabilities,"loaded":loaded,"composition":comp,
        "readback":readback,"reopened_readback":reopened,"full_pixels":full.data,"half_pixels":half.data,
        "legacy_modules_loaded":legacy,"source_effect_support_added":false,"all_source_effects_supported":false});
    std::fs::write(
        out.join("summary.json"),
        serde_json::to_string_pretty(&audit).unwrap(),
    )
    .unwrap();
    println!(
        "Engine host proof: two images, full/half previews, exact Layer readback, save/reopen and 12 legacy modules"
    );
}
