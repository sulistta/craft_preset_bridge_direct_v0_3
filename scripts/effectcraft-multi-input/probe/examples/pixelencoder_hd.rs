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
    session.execute("comp.new",json!({"width":1920,"height":1080,"duration":2,"frameRate":30,"name":"Original HD pixelencoder workload"})).unwrap();
    let target=session.execute("layer.newSolid",json!({"color":"#808080"})).unwrap()["layer"].as_u64().unwrap();
    let cid=session.active_comp_id().unwrap();
    let applied=session.execute("effect.apply",json!({"layer":target,"effect":"org.craftbridge.pixelencoder"})).unwrap();
    let path=applied["paths"][0].as_str().unwrap();
    for (id,value) in [("brightness",json!(0.)),("contrast",json!(100.)),("foreground",json!([1.,0.,0.,1.])),("background",json!([0.,0.,1.,1.]))] {
        session.execute("prop.set",json!({"layer":target,"path":format!("{path}/{id}"),"value":value})).unwrap();
    }
    let started=std::time::Instant::now();let frame=session.render(cid,Tick::ZERO,RenderOpts::default());
    let elapsed=started.elapsed().as_secs_f64();
    assert_eq!((frame.width,frame.height),(1920,1080));
    assert!(frame.data.iter().flatten().all(|v|v.is_finite()));
    let visible=frame.data.iter().filter(|p|p[0]>0. && p[2]==0.).count();
    let transparent=frame.data.iter().filter(|p|p[2]>0. && p[0]==0.).count();
    assert!(visible>0 && transparent>0);
    println!("{}",json!({"api":2,"width":frame.width,"height":frame.height,"seconds":elapsed,"foreground_pixels":visible,"background_pixels":transparent,"workload":"Original segment glyph tiles, uniform source, neutral brightness/contrast, red/blue markers","adobe_visual_comparison":false}));
}
