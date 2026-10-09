(module
 (memory (export "memory") 8)
 (data (i32.const 16) "{\"api\":4,\"bridge_host_revision\":3,\"id\":\"org.craftbridge.test.temporal\",\"name\":\"Original frame-hold transport probe\",\"category\":\"Bridge Validation\",\"version\":\"0.1.0\",\"description\":\"Original transport test only. Copies preceding-effect pixels at a held source time; no Adobe effect map.\",\"params\":[{\"id\":\"skip\",\"name\":\"Frames to skip (test contract)\",\"type\":\"slider\",\"default\":0.0,\"min\":0.0,\"max\":1024.0}],\"temporal_inputs\":[{\"id\":\"held\",\"mode\":\"frame_hold\",\"parameter\":\"skip\",\"multiple\":1,\"edge\":\"clamp\"}]}")
 (func (export "ec_api_version") (result i32) i32.const 4)
 (func (export "ec_manifest_ptr") (result i32) i32.const 16)
 (func (export "ec_manifest_len") (result i32) i32.const 505)
 (func (export "ec_alloc") (param $n i32) (result i32)
  local.get $n i32.const 458752 i32.gt_u if (result i32) i32.const 0 else i32.const 65536 end)
 (func (export "ec_render_v4") (param $px i32) (param $w i32) (param $h i32)
  (param $params i32) (param $np i32) (param $time f64) (param $scale f64)
  (param $table i32) (param $nt i32) (param $timing i32) (result i32)
  local.get $nt i32.const 2 i32.ne if i32.const 1 return end
  local.get $np i32.const 1 i32.ne if i32.const 1 return end
  local.get $table i32.load offset=80 i32.const -2147483648 i32.ne if i32.const 1 return end
  local.get $table i64.load offset=84 i64.eqz i32.eqz if i32.const 1 return end
  local.get $table i32.load offset=92 i32.const 4 i32.ne if i32.const 1 return end
  local.get $table i32.load offset=100 local.get $w i32.ne if i32.const 1 return end
  local.get $table i32.load offset=104 local.get $h i32.ne if i32.const 1 return end
  local.get $table f64.load offset=152 local.get $table f64.load offset=152 f64.ne if i32.const 1 return end
  local.get $px local.get $table i32.load offset=96
  local.get $w local.get $h i32.mul i32.const 16 i32.mul memory.copy
  i32.const 0))
