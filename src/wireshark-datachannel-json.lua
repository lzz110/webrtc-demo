--[[
  Wireshark Lua 解析器：将 WebRTC DataChannel 上的 JSON 载荷解析为树状显示
  适用于 SCTP PPID 51 (WebRTC String) 中的 {"type":"msg", "id":"...", "text":"..."} 等格式

  加载方式：
    1. 编辑 → 首选项 → Lua → 脚本路径：添加本文件所在目录，或
    2. 编辑 → 首选项 → Lua → 启用 “Default” 并填入本文件完整路径，或
    3. 终端：wireshark -X lua_script:/path/to/wireshark-datachannel-json.lua

  依赖：DTLS 已解密，SCTP 已解析（需配置 TLS Pre-Master-Secret log）
]]

local dc_json_proto = Proto("WebRTC_DataChannel_JSON", "WebRTC DataChannel JSON")

local f_type   = ProtoField.string("dc_json.type", "Type")
local f_id     = ProtoField.string("dc_json.id", "Message ID")
local f_text   = ProtoField.string("dc_json.text", "Text")
local f_name   = ProtoField.string("dc_json.name", "File Name")
local f_size   = ProtoField.uint32("dc_json.size", "File Size")
local f_raw    = ProtoField.string("dc_json.raw", "Raw JSON")

dc_json_proto.fields = { f_type, f_id, f_text, f_name, f_size, f_raw }

-- 简单从 JSON 字符串中提取 "key":"value"（value 可为字符串或数字）
local function extract_json_string(str, key)
  local pattern = '"' .. key .. '"%s*:%s*"([^"]*)"'
  return string.match(str, pattern)
end

local function extract_json_number(str, key)
  local pattern = '"' .. key .. '"%s*:%s*(%d+)'
  return tonumber(string.match(str, pattern))
end

function dc_json_proto.dissector(buffer, pinfo, tree)
  local len = buffer:len()
  if len < 10 then return 0 end

  local payload = buffer:range(0, len):string()
  if not payload or #payload < 10 then return 0 end

  -- 只处理看起来像本 demo 的 JSON（type / msg / file / ack）
  if not payload:match('"type"%s*:') then return 0 end

  pinfo.cols.protocol:set("WebRTC_DataChannel_JSON")

  local subtree = tree:add(dc_json_proto, buffer(), "WebRTC DataChannel JSON")

  local typ = extract_json_string(payload, "type")
  if typ then
    subtree:add(f_type, typ)
    if typ == "msg" then
      local id  = extract_json_string(payload, "id")
      local text = extract_json_string(payload, "text")
      if id  then subtree:add(f_id, id) end
      if text then subtree:add(f_text, text) end
    elseif typ == "file" then
      local id   = extract_json_string(payload, "id")
      local name = extract_json_string(payload, "name")
      local size = extract_json_number(payload, "size")
      if id   then subtree:add(f_id, id) end
      if name then subtree:add(f_name, name) end
      if size then subtree:add(f_size, size) end
    elseif typ == "ack" then
      local id = extract_json_string(payload, "id")
      if id then subtree:add(f_id, id) end
    end
  end

  subtree:add(f_raw, payload)

  return len
end

-- 注册到 SCTP Payload Protocol Identifier 51 (WebRTC String)
local sctp_ppi = DissectorTable.get("sctp.ppi")
if sctp_ppi then
  sctp_ppi:add(51, dc_json_proto)
end
