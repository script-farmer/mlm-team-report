"""
D3.js 层级树渲染——替代 pyvis 的简陋布局。
每代严格同一水平线，连线为阶梯直角折线。
"""
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"

# 布局参数
NODE_W = 100       # 节点宽度
NODE_H = 48        # 节点高度
LAYER_H = 140      # 层高（每代间距）
MIN_NODE_GAP = 20  # 同代节点最小间距


def build_d3_tree(G, root_id):
    """将 networkx 子图转为 D3 层级树 JSON"""
    def _build(node_id):
        children_list = []
        for child in sorted(G.successors(node_id)):
            children_list.append(_build(child))
        data = G.nodes[node_id]
        return {
            "id": node_id,
            "name": data.get("name", "未知"),
            "subtree": data.get("subtree_size", 1),
            "is_external": data.get("is_external", False),
            "children": children_list,
        }
    return _build(root_id)


def render_tree_html(tree_data, max_subtree, output_path, title="推荐关系树"):
    """生成 D3 树形 HTML——根在上方，逐代向下，直角阶梯连线"""
    tree_json = json.dumps(tree_data, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ margin:0; overflow:hidden; font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#d0d0d0; }}
  #svg {{ width:100vw; height:100vh; outline:6px solid #333; outline-offset:-6px; box-sizing:border-box; pointer-events:all; }}
  .node rect {{ stroke-width:2; rx:6; ry:6; cursor:pointer; }}
  .node .id-text {{ font-weight:bold; font-size:13px; fill:#222; text-anchor:middle; }}
  .node .name-text {{ font-size:11px; fill:#555; text-anchor:middle; }}
  .node .count-text {{ font-size:9px; fill:#888; text-anchor:middle; }}
  .link {{ fill:none; stroke:#bbb; stroke-width:1.5; }}
  .root rect {{ stroke:#FF5722; stroke-width:3.5; }}
  .tooltip {{ position:absolute; padding:8px 12px; background:rgba(0,0,0,0.82);
    color:#fff; border-radius:6px; font-size:12px; pointer-events:none; opacity:0;
    transition:opacity 0.15s; max-width:260px; }}
</style>
</head>
<body>
<svg id="svg"></svg>
<div class="tooltip" id="tooltip"></div>

<script src="https://cdn.bootcdn.net/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>window.d3||document.write('<script src="https://d3js.org/d3.v7.min.js"><\\/script>');</script>
<script>
const treeData = {tree_json};
const maxSubtree = {max_subtree};
const NODE_W = {NODE_W}, NODE_H = {NODE_H};

function subtreeColor(ss) {{
    if (ss >= 1000) return "#FFAAA5";
    if (ss >= 200)  return "#FFD3B6";
    if (ss >= 50)   return "#FFE5D9";
    if (ss >= 10)   return "#C7CEEA";
    return "#B5EAD7";
}}

const svg = d3.select("#svg");
const g = svg.append("g");
const tooltip = d3.select("#tooltip");
const zoom = d3.zoom().scaleExtent([0.02,15]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

// D3 树布局
const root = d3.hierarchy(treeData);
d3.tree()
  .nodeSize([{NODE_W + MIN_NODE_GAP}, {LAYER_H}])
  .separation((a,b) => a.parent===b.parent ? 1.3 : 1.8)
(root);

// 构建 ID → 节点 映射表
const nodeMap = new Map();
root.each(d => {{ if (d.data.id !== 0) nodeMap.set(String(d.data.id), d); }});

// 计算边界
let minX=Infinity, maxX=-Infinity, maxY=0;
root.each(d => {{
  if (d.data.id === 0) return;
  minX = Math.min(minX, d.x);
  maxX = Math.max(maxX, d.x);
  maxY = Math.max(maxY, d.y);
}});
const pad = 80;
const treeW = maxX - minX + pad*2;
const treeH = maxY + pad*2;

// 直角阶梯连线
function elbowPath(d) {{
  const sx = d.source.x, sy = d.source.y + NODE_H/2;
  const tx = d.target.x, ty = d.target.y - NODE_H/2;
  const my = sy + (ty - sy) * 0.55;
  return "M"+sx+","+sy+" L"+sx+","+my+" L"+tx+","+my+" L"+tx+","+ty;
}}

// 边
g.selectAll(".link").data(root.links().filter(l => l.source.data.id !== 0)).join("path")
  .attr("class","link").attr("d", elbowPath);

// 节点
const realNodes = root.descendants().filter(d => d.data.id !== 0);
const nodeG = g.selectAll(".node").data(realNodes).join("g")
  .attr("class", d => "node" + (d.depth===0?" root":""))
  .attr("transform", d => "translate("+d.x+","+d.y+")")
  .on("mouseenter", (evt,d) => {{
    tooltip.style("opacity",1).html(
      "<b>ID:</b> "+d.data.id+"<br><b>姓名:</b> "+d.data.name+"<br><b>旗下:</b> "+d.data.subtree+"人");
  }})
  .on("mousemove", evt => tooltip.style("left",(evt.pageX+12)+"px").style("top",(evt.pageY-10)+"px"))
  .on("mouseleave", () => tooltip.style("opacity",0));

const hw = NODE_W/2, hh = NODE_H/2;

// 底层彩色框
nodeG.append("rect")
  .attr("class","color-box")
  .attr("x",-hw).attr("y",-hh).attr("width",NODE_W).attr("height",NODE_H)
  .attr("fill", d => subtreeColor(d.data.subtree))
  .attr("stroke", d => d.depth===0 ? "#FF5722" : subtreeColor(d.data.subtree));

// 文字
nodeG.append("text").attr("class","id-text").attr("y",-7)
  .text(d => typeof d.data.id === 'string' && d.data.id.length > 10
    ? d.data.id.slice(0,8)+'...' : d.data.id);
nodeG.append("text").attr("class","name-text").attr("y",9).text(d => d.data.name);
nodeG.append("text").attr("class","count-text").attr("y",21).text(d => d.data.subtree>=2 ? "("+d.data.subtree+"人)" : "");

// ====== 点击高亮（D3 click 事件） ======
let selectedRootId = null;

nodeG.style("cursor","pointer")
  .on("click", function(evt, d) {{
    if (evt.defaultPrevented) return;
    evt.stopPropagation();
    const nodeId = String(d.data.id);
    if (selectedRootId === nodeId) {{
      resetHighlight();
    }} else {{
      highlightSubtree(nodeId);
    }}
  }});

function highlightSubtree(nodeId) {{
  selectedRootId = nodeId;
  const d = nodeMap.get(nodeId);
  if (!d) return;
  const sel = new Set();
  (function collect(n) {{
    sel.add(String(n.data.id));
    if (n.children) n.children.forEach(collect);
  }})(d);
  nodeG.attr("opacity", n => sel.has(String(n.data.id)) ? 1 : 0.12);
  nodeG.select("rect.color-box")
    .attr("stroke", n => String(n.data.id)===nodeId ? "#FF5722"
      : (sel.has(String(n.data.id)) ? subtreeColor(n.data.subtree) : "#ddd"));
  g.selectAll(".link")
    .attr("opacity", l => sel.has(String(l.target.data.id)) ? 1 : 0.06)
    .attr("stroke", l => sel.has(String(l.target.data.id)) ? "#FF9800" : "#bbb")
    .attr("stroke-width", l => sel.has(String(l.target.data.id)) ? 2.5 : 1.2);
}}

function resetHighlight() {{
  selectedRootId = null;
  nodeG.attr("opacity", 1);
  nodeG.select("rect.color-box")
    .attr("stroke", n => n.depth===0 ? "#FF5722" : subtreeColor(n.data.subtree));
  g.selectAll(".link")
    .attr("opacity", 1)
    .attr("stroke", "#bbb")
    .attr("stroke-width", 1.5);
}}

// 点击空白区域恢复
svg.on("click", function(evt) {{
  if (evt.target === svg.node() && selectedRootId) resetHighlight();
}});

// 初始缩放
const fitScale = Math.min(window.innerWidth/treeW, (window.innerHeight-80)/treeH);
const initScale = Math.max(0.18, Math.min(0.95, fitScale));
svg.call(zoom.transform, d3.zoomIdentity
  .translate(window.innerWidth/2 - (minX+maxX)/2*initScale, pad*initScale + 20)
  .scale(initScale));
</script>
</body>
</html>'''

    with open(str(output_path), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  D3 树形图已保存: {output_path}")
