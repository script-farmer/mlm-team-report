"""
从推荐关系.xlsx 生成 D3 可视化团队推荐结构图。
输出两个文件：
  - output/团队全网络.html    全公司推荐关系图
  - output/团队子树.html      最大的推荐人的子树图
"""
import pandas as pd
import networkx as nx
from pathlib import Path
from d3_render import build_d3_tree, render_tree_html

BASE = Path(__file__).parent
OUTPUT_DIR = BASE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 1. 加载数据 =====
df = pd.read_excel(BASE / "推荐关系.xlsx")
if "会员ID" in df.columns:
    df.columns = ["member_id", "member_name", "ref_id", "ref_name"]
else:
    df.columns = ["member_id", "member_name", "ref_id", "ref_name"]

# 清洗
df["member_id"] = df["member_id"].astype(str).str.strip()
df["ref_id"]   = df["ref_id"].astype(str).str.strip()
df["member_name"] = df["member_name"].fillna("未知").astype(str).str.strip()
df["ref_name"]    = df["ref_name"].fillna("未知").astype(str).str.strip()

print(f"数据: {len(df)} 条记录, {df['member_id'].nunique()} 个会员")

# ===== 2. 构建有向图 =====
G = nx.DiGraph()
member_names = {}

for _, row in df.iterrows():
    mid = row["member_id"]
    member_names[mid] = row["member_name"]
    G.add_node(mid, name=row["member_name"], is_external=False)

for _, row in df.iterrows():
    mid, rid = row["member_id"], row["ref_id"]
    if rid and rid != "0" and rid != "nan" and rid in member_names:
        G.add_edge(rid, mid)
    elif rid and rid != "0" and rid != "nan":
        # 推荐人不在会员列表中（外部推荐人）
        if rid not in G:
            G.add_node(rid, name=row["ref_name"], is_external=True)
        G.add_edge(rid, mid)

all_ids = set(df["member_id"])
root_ids = [n for n in G.nodes() if G.in_degree(n) == 0]
print(f"总节点: {G.number_of_nodes()}, 根节点: {len(root_ids)}")

# 计算子树大小
def calc_subtree_size(node, visited=None):
    if visited is None:
        visited = set()
    if node in visited:
        return 0
    visited.add(node)
    count = 1
    for child in G.successors(node):
        count += calc_subtree_size(child, visited)
    return count

for node in G.nodes():
    G.nodes[node]["subtree_size"] = calc_subtree_size(node)

# ===== 3. 渲染 D3 图 =====
max_size = max(G.nodes[n].get("subtree_size", 1) for n in G.nodes())
print(f"最大子树规模: {max_size}")

# 多根节点 → 虚拟根节点包装
trees = []
for rid in sorted(root_ids, key=lambda n: G.nodes[n].get("subtree_size", 0), reverse=True):
    trees.append(build_d3_tree(G, rid))

if len(trees) == 1:
    full_tree = trees[0]
else:
    full_tree = {
        "id": "__root__",
        "name": "全公司",
        "subtree": sum(G.nodes[n].get("subtree_size", 1) for n in root_ids),
        "is_external": False,
        "children": trees,
    }

render_tree_html(full_tree, max_size, str(OUTPUT_DIR / "团队全网络.html"), title="团队推荐网络全图")
print(f"全网络图已生成: {OUTPUT_DIR / '团队全网络.html'}")

# 最大子树图
biggest_root = max(root_ids, key=lambda n: G.nodes[n].get("subtree_size", 0))
subtree = build_d3_tree(G, biggest_root)
render_tree_html(subtree, G.nodes[biggest_root]["subtree_size"],
                 str(OUTPUT_DIR / "团队子树.html"),
                 title=f"团队子树 — {G.nodes[biggest_root]['name']}")
print(f"子树图已生成: {OUTPUT_DIR / '团队子树.html'}")

# ===== 4. 统计信息 =====
print(f"\n{'='*50}")
print("推荐网络统计")
print(f"{'='*50}")
print(f"总会员数: {len(all_ids)}")
print(f"总推荐关系: {G.number_of_edges()}")
print(f"根节点数（顶层推荐人）: {len(root_ids)}")

# Top 10 最大子树
top_roots = sorted(root_ids, key=lambda n: G.nodes[n].get("subtree_size", 0), reverse=True)[:10]
print(f"\nTop 10 最大推荐人:")
for i, rid in enumerate(top_roots):
    name = G.nodes[rid]["name"]
    size = G.nodes[rid]["subtree_size"]
    direct = G.out_degree(rid)
    print(f"  {i+1}. {name}(ID:{rid}) — 团队{size}人, 直推{direct}人")
