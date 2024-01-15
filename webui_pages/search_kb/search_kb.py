import streamlit as st
from webui_pages.utils import *
from st_aggrid import AgGrid, JsCode
from st_aggrid.grid_options_builder import GridOptionsBuilder
import pandas as pd
from server.knowledge_base.utils import get_file_path, LOADER_DICT
from server.knowledge_base.kb_service.base import get_kb_details, get_kb_file_details
from typing import Literal, Dict, Tuple
from configs import (kbs_config,
                     EMBEDDING_MODEL, DEFAULT_VS_TYPE,
                     CHUNK_SIZE, OVERLAP_SIZE, ZH_TITLE_ENHANCE)
from server.utils import list_embed_models, list_online_embed_models
import os
import time

# SENTENCE_SIZE = 100

cell_renderer = JsCode("""function(params) {if(params.value==true){return '✓'}else{return '×'}}""")


def config_aggrid(
        df: pd.DataFrame,
        columns: Dict[Tuple[str, str], Dict] = {},
        selection_mode: Literal["single", "multiple", "disabled"] = "single",
        use_checkbox: bool = False,
) -> GridOptionsBuilder:
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("No", width=40)
    for (col, header), kw in columns.items():
        gb.configure_column(col, header, wrapHeaderText=True, **kw)
    gb.configure_selection(
        selection_mode=selection_mode,
        use_checkbox=use_checkbox,
        # pre_selected_rows=st.session_state.get("selected_rows", [0]),
    )
    gb.configure_pagination(
        enabled=True,
        paginationAutoPageSize=False,
        paginationPageSize=10
    )
    return gb


root_node = None


def search_kb(api: ApiRequest, is_lite: bool = None):
    def get_active_path():
        if 'active_path' not in st.session_state:
            st.session_state["active_path"] = []
        return st.session_state["active_path"]

    def reset_active_path(path):
        get_active_path().clear()
        print("before extend:{}".format(get_active_path()))
        get_active_path().extend(path)
        print("after extend:{}".format(get_active_path()))

    def append_path(path):
        print("before append:{}".format(get_active_path()))
        get_active_path().append(path)
        print("after append:{}".format(get_active_path()))

    class TreeNode:
        def __init__(self, key, value, parent_path):
            self.key = key
            self.value = value
            self.children = []
            self.path = list(parent_path)
            self.path.append(key)
            append_path(key)

        def get_key(self):
            return self.key

        def get_value(self):
            return self.value

        def get_children(self):
            return self.children

        def set_children(self, children):
            self.children = children

        def get_path(self):
            return self.path

        def search_data(self):
            print("current path:{}".format(self.get_path()))
            reset_active_path(self.get_path())
            data_list = api.search_kb_docs(query=self.value, knowledge_base_name=st.session_state["selected_kb_info"])
            children = []
            for index, child_data in enumerate(data_list):
                part_name = self.get_key() + '-' + str(index + 1)
                child = TreeNode(part_name, child_data, self.get_path())
                children.append(child)
            self.set_children(children)

    try:
        kb_list = {x["kb_name"]: x for x in get_kb_details()}
    except Exception as e:
        st.error(
            "获取知识库信息错误，请检查是否已按照 `README.md` 中 `4 知识库初始化与迁移` 步骤完成初始化或迁移，或是否为数据库连接错误。")
        st.stop()
    kb_names = list(kb_list.keys())

    if "selected_kb_name" in st.session_state and st.session_state["selected_kb_name"] in kb_names:
        selected_kb_index = kb_names.index(st.session_state["selected_kb_name"])
    else:
        selected_kb_index = 0

    if "selected_kb_info" not in st.session_state:
        st.session_state["selected_kb_info"] = ""

    def format_selected_kb(kb_name: str) -> str:
        if kb := kb_list.get(kb_name):
            return f"{kb_name} ({kb['vs_type']} @ {kb['embed_model']})"
        else:
            return kb_name

    selected_kb = st.selectbox(
        "请选择知识库：",
        kb_names,
        format_func=format_selected_kb,
        index=selected_kb_index
    )

    def print_child(parent: TreeNode):
        if len(parent.get_children()) == 0:
            return
        cols = st.columns(len(parent.get_children()))
        for index, col in enumerate(cols):
            print_tree_node(col, parent.get_children()[index], True)

    def print_tree_node(part_st, node: TreeNode, disabled: bool):
        print("active_path:{}".format(get_active_path()))
        print("node key:{}".format(node.get_key()))
        if node.get_key() not in get_active_path():
            print("不在数组中")
            return
        container = part_st.container(border=True)
        with container:
            child_search_info = container.text_area(
                node.get_key(),
                value=node.get_value(),
                key=node.get_key(),
                disabled=disabled
            )
            child_submit_search = container.button(
                "搜索" + node.get_key(),
                # disabled=not bool(kb_name),
                use_container_width=True,
                on_click=node.search_data
            )
        print_child(node)

    if selected_kb:
        kb = selected_kb
        st.session_state["selected_kb_info"] = kb_list[kb]['kb_info']
        if 'root_node' not in st.session_state:
            st.session_state["root_node"] = TreeNode("文档", "", [])
        print_tree_node(st, st.session_state["root_node"], False)
