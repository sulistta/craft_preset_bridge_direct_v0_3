//! Original HD workload, not Adobe visual comparison or a general benchmark.
use effectcraft_engine::Session;
use effectcraft_render::RenderOpts;
use effectcraft_time::Tick;
use serde_json::json;
fn main() {
    let module=std::env::args().nth(1).expect("module path");
    let mut session=Session::new();session.plugin_loader=Some(effectcraft_plugin::loader);
    assert_eq!(session.execute("effect.plugins.load",json!({"path":module})).unwrap()["loaded"][0]["api"],4);
    session.execute("file.projectSettings",json!({"bitDepth":32})).unwrap();
    session.execute("comp.new",json!({"width":1920,"height":1080,"duration":2,"frameRate":30,"name":"Original HD geometric workload"})).unwrap();
    let target=session.execute("layer.newSolid",json!({"color":"#404040"})).unwrap()["layer"].as_u64().unwrap();
    let cid=session.active_comp_id().unwrap();
    let applied=session.execute("effect.apply",json!({"layer":target,"effect":"org.craftbridge.geometric"})).unwrap();
    let path=applied["paths"][0].as_str().unwrap();
    // Saved real snapshot defaults, but synthetic pixels; keep=false exposes failures.
    session.execute("prop.set",json!({"layer":target,"path":format!("{path}/keep"),"value":false})).unwrap();
    let started=std::time::Instant::now();let frame=session.render(cid,Tick::ZERO,RenderOpts::default());
    let elapsed=started.elapsed().as_secs_f64();
    assert_eq!((frame.width,frame.height),(1920,1080));
    assert!(frame.data.iter().flatten().all(|v|v.is_finite()));
    let visible=frame.data.iter().filter(|p|p[3]>0.).count();
    let transparent=frame.data.iter().filter(|p|p[3]==0.).count();
    assert!(visible>0 && transparent>0);
    println!("{}",json!({"api":4,"width":frame.width,"height":frame.height,"seconds":elapsed,"visible_pixels":visible,"transparent_pixels":transparent,"workload":"1000 original triangles, one recursion, uniform source, no background","adobe_visual_comparison":false}));
}
