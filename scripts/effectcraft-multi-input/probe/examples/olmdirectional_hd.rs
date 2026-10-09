//! Original HD workload, not Adobe visual comparison or a general benchmark.
use effectcraft_engine::Session;
use effectcraft_render::RenderOpts;
use effectcraft_time::Tick;
use serde_json::json;
fn main() {
    let module=std::env::args().nth(1).expect("module path");
    let mut session=Session::new();session.plugin_loader=Some(effectcraft_plugin::loader);
    assert_eq!(session.execute("effect.plugins.load",json!({"path":module})).unwrap()["loaded"][0]["api"],2);
    session.execute("file.projectSettings",json!({"bitDepth":32})).unwrap();
    session.execute("comp.new",json!({"width":1920,"height":1080,"duration":2,"frameRate":30,"name":"Original HD OLM-style anisotropic workload"})).unwrap();
    let target=session.execute("layer.newSolid",json!({"color":"#808080"})).unwrap()["layer"].as_u64().unwrap();
    let cid=session.active_comp_id().unwrap();
    let applied=session.execute("effect.apply",json!({"layer":target,"effect":"org.craftbridge.olmdirectional"})).unwrap();
    let path=applied["paths"][0].as_str().unwrap();
    session.execute("prop.set",json!({"layer":target,"path":format!("{path}/front"),"value":140.})).unwrap();
    let started=std::time::Instant::now();let frame=session.render(cid,Tick::ZERO,RenderOpts::default());
    let elapsed=started.elapsed().as_secs_f64();
    assert_eq!((frame.width,frame.height),(1920,1080));
    assert!(frame.data.iter().flatten().all(|v|v.is_finite()));
    let expected=128./255.;
    assert!(frame.data.iter().all(|p|p[3]==1. && p[..3].iter().all(|v|(*v as f64-expected).abs()<1e-6)));
    println!("{}",json!({"api":2,"width":frame.width,"height":frame.height,"seconds":elapsed,"all_uniform_expected_pixels_verified":true,"workload":"Original fully opaque uniform detail, front blur 140, angle 106, inactive noise input","adobe_visual_comparison":false}));
}
