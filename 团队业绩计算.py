#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直销推荐网络 — 团队累计营业额计算（通用版）
============================================
使用方法:
  python 团队业绩计算.py                  # 生成全量团队业绩汇总
  python 团队业绩计算.py --id 335         # 查询指定会员团队业绩

数据源模板（放在脚本同目录下）:
  推荐关系.xlsx  — 4列: 会员ID, 会员姓名, 推荐人ID, 推荐人姓名
  销售额.xlsx    — 3列: 会员ID, 会员姓名, 营业额

支持 .xlsx / .xls / .csv 格式
"""

import sys
import os
import pandas as pd
import networkx as nx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_file(*names):
    """在脚本目录查找文件，支持多种格式"""
    for name in names:
        for ext in ['.xlsx', '.xls', '.csv']:
            path = os.path.join(SCRIPT_DIR, name + ext)
            if os.path.exists(path):
                return path
    return None


def read_table(path):
    """读取表格，自动处理格式"""
    if path.endswith('.csv'):
        return pd.read_csv(path, encoding='utf-8-sig')
    else:
        return pd.read_excel(path)


def load_data():
    """加载推荐关系和销售额两个数据源"""
    # 数据源1：推荐关系
    rel_path = find_file('推荐关系', '推荐关系数据', '推荐关系表')
    if not rel_path:
        print("[错误] 未找到「推荐关系.xlsx」，请放入以下4列数据：")
        print("  会员ID | 会员姓名 | 推荐人ID | 推荐人姓名")
        sys.exit(1)

    rel_df = read_table(rel_path)
    rel_df = rel_df.iloc[:, [0, 1, 2, 3]].copy()
    rel_df.columns = ['会员ID', '会员姓名', '推荐人ID', '推荐人姓名']
    rel_df['会员ID'] = rel_df['会员ID'].astype(str).str.strip()
    rel_df['推荐人ID'] = rel_df['推荐人ID'].astype(str).str.strip()
    rel_df['会员姓名'] = rel_df['会员姓名'].astype(str).str.strip()
    rel_df['推荐人姓名'] = rel_df['推荐人姓名'].astype(str).str.strip()
    print(f"[OK] 推荐关系: {len(rel_df)} 条 ({os.path.basename(rel_path)})")

    # 数据源2：销售额
    sales_path = find_file('销售额', '销售数据', '营业额')
    if not sales_path:
        print("[错误] 未找到「销售额.xlsx」，请放入以下3列数据：")
        print("  会员ID | 会员姓名 | 营业额")
        sys.exit(1)

    sales_df = read_table(sales_path)
    sales_df = sales_df.iloc[:, [0, 1, 2]].copy()
    sales_df.columns = ['会员ID', '会员姓名', '营业额']
    sales_df['会员ID'] = sales_df['会员ID'].astype(str).str.strip()
    sales_df['营业额'] = pd.to_numeric(sales_df['营业额'], errors='coerce').fillna(0)
    print(f"[OK] 销售额数据: {len(sales_df)} 条 ({os.path.basename(sales_path)})")

    return rel_df, sales_df


def build_graph(rel_df):
    """构建推荐关系有向图"""
    G = nx.DiGraph()

    for _, row in rel_df.iterrows():
        mid = row['会员ID']
        rid = row['推荐人ID']
        mname = row['会员姓名']
        rname = row['推荐人姓名']

        G.add_node(mid, name=mname)
        if rid and rid != '0' and rid != 'nan':
            G.add_node(rid, name=rname)
            if mid != rid:
                G.add_edge(rid, mid)

    # 检测循环
    try:
        cycles = list(nx.simple_cycles(G))
        if cycles:
            print(f"[注意] {len(cycles)} 个推荐循环，已自动忽略循环边")
    except Exception:
        pass

    # 根节点
    all_members = set(rel_df['会员ID'])
    all_refs = set(rel_df['推荐人ID']) - {'0', '', 'nan'}
    roots = all_refs - all_members
    print(f"[OK] 网络: {G.number_of_nodes()} 节点, {G.number_of_edges()} 边, {len(roots)} 个根节点")

    return G


def compute_all(G, sales_map, name_map):
    """全量计算所有会员的团队累计营业额"""
    results = []

    for node in G.nodes():
        try:
            descendants = nx.descendants(G, node)
        except Exception:
            descendants = set()

        own = sales_map.get(node, 0)
        down = sum(sales_map.get(d, 0) for d in descendants)
        direct = len(list(G.successors(node)))

        results.append({
            '会员ID': node,
            '会员姓名': name_map.get(node, ''),
            '直推人数': direct,
            '团队总人数': 1 + len(descendants),
            '个人营业额': round(own, 2),
            '下线营业额': round(down, 2),
            '团队累计营业额': round(own + down, 2),
        })

    return pd.DataFrame(results).sort_values('团队累计营业额', ascending=False)


def query_one(G, sales_map, name_map, member_id):
    """查询单个会员"""
    member_id = str(member_id).strip()
    if member_id not in G:
        print(f"[错误] 会员ID「{member_id}」不在推荐网络中")
        return

    try:
        descendants = nx.descendants(G, member_id)
    except Exception:
        descendants = set()

    own = sales_map.get(member_id, 0)
    down = sum(sales_map.get(d, 0) for d in descendants)
    direct_children = list(G.successors(member_id))

    print(f"\n{'=' * 55}")
    print(f"  {member_id}  {name_map.get(member_id, '')}")
    print(f"{'=' * 55}")
    print(f"  直推人数:          {len(direct_children):>8}")
    print(f"  团队总人数(含自身): {1 + len(descendants):>8}")
    print(f"  个人营业额:        {own:>12,.2f}")
    print(f"  下线营业额:        {down:>12,.2f}")
    print(f"  团队累计营业额:    {own + down:>12,.2f}")

    # 递归展开下线
    def expand(node, level=1):
        items = []
        for child in G.successors(node):
            items.append((level, child, name_map.get(child, ''), sales_map.get(child, 0)))
            items.extend(expand(child, level + 1))
        return items

    team = expand(member_id)
    if team:
        print(f"\n  团队明细 (共{len(team)}人):")
        print(f"  {'层级':<5} {'会员ID':<12} {'姓名':<14} {'营业额':>12}")
        print(f"  {'-'*45}")
        for lv, mid, name, val in team:
            print(f"  {'L'+str(lv):<5} {mid:<12} {name:<14} {val:>12,.2f}")


def cmd_query_loop(G, sales_map, name_map):
    """交互式查询模式"""
    print("\n" + "=" * 50)
    print("  团队业绩查询")
    print("  输入会员ID查询，输入 q 退出")
    print("=" * 50)

    while True:
        try:
            uid = input("\n会员ID > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if uid.lower() == 'q':
            break
        if uid:
            query_one(G, sales_map, name_map, uid)


def main():
    print("=" * 50)
    print("  团队累计营业额计算")
    print("=" * 50)

    # 加载
    rel_df, sales_df = load_data()

    # 构建图（使用字符串ID，兼容纯数字和混合ID）
    G = build_graph(rel_df)

    # 构建映射
    sales_map = dict(zip(sales_df['会员ID'], sales_df['营业额']))
    name_map = {}
    for _, r in rel_df.iterrows():
        name_map[r['会员ID']] = r['会员姓名']
    for _, r in sales_df.iterrows():
        if r['会员ID'] not in name_map:
            name_map[r['会员ID']] = r['会员姓名']

    # 判断模式
    args = sys.argv[1:]

    if '--id' in args:
        idx = args.index('--id')
        uid = args[idx + 1] if idx + 1 < len(args) else input("请输入会员ID: ").strip()
        query_one(G, sales_map, name_map, uid)

    elif '--query' in args or '-q' in args:
        cmd_query_loop(G, sales_map, name_map)

    else:
        # 全量汇总
        print("\n正在计算全部会员团队业绩...")
        result_df = compute_all(G, sales_map, name_map)

        out_path = os.path.join(SCRIPT_DIR, '团队业绩汇总.xlsx')
        with pd.ExcelWriter(out_path, engine='xlsxwriter') as writer:
            result_df.to_excel(writer, sheet_name='全部团队业绩', index=False)
            result_df.head(200).to_excel(writer, sheet_name='TOP200', index=False)

            for sn in ['全部团队业绩', 'TOP200']:
                ws = writer.sheets[sn]
                ws.set_column('A:A', 14)
                ws.set_column('B:B', 16)
                ws.set_column('C:D', 12)
                ws.set_column('E:G', 18)

        print(f"\n[完成] 输出: {out_path}")
        print(f"  共 {len(result_df)} 人")
        print(f"\n  Top 10 团队业绩:")
        for _, row in result_df.head(10).iterrows():
            print(f"  {row['会员ID']:<12} {row['会员姓名']:<14} "
                  f"团队{int(row['团队总人数'])}人  "
                  f"累计{row['团队累计营业额']:>14,.2f}")


if __name__ == '__main__':
    main()
