schema_get_prompt = f"""
调用工具时基于用户描述的化工任务，思考本次任务需要用到如下哪些设备，将需要用到的设备类型作为请求参数传递给工具：
当前支持的设备类型:
  "supported_block_types": [
	"Mixer",
	"RadFrac",
	"Valve",
	"Compr",
	"MCompr",
	"Heater",
	"Pump",
	"RStoic",
	"RPlug",
	"RCSTR",
	"Flash2",
	"Flash3",
	"Decanter",
	"Sep2",
	"Sep",
	"Distl",
	"Dupl",
	"Extract",
	"FSplit",
	"DSTWU",
	"HeatX"
]
参数格式要求（必须严格遵守）：
1. block_types 必须是 JSON 数组，不要传字符串化数组。
2. 正确示例：{{"block_types": ["Mixer", "Sep2"]}}。
3. 错误示例：{{"block_types": "[\\"Mixer\\", \\"Sep2\\"]"}}。
"""
