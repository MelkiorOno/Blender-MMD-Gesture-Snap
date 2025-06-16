bl_info = {
    "name": "MMD Gesture Snap",
    "author": "火茶",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Gesture",
    "description": "记录和应用手部动作",
    "category": "Animation",
}

import bpy
import json
import os
from mathutils import Vector, Quaternion, Matrix
from bpy.types import Panel, Operator
from bpy.props import StringProperty, EnumProperty, StringProperty, BoolProperty

# 手部骨骼名称字典
HAND_BONES = {
    'LEFT': [
        "親指０.L", "親指１.L", "親指２.L",
        "人指１.L", "人指２.L", "人指３.L",
        "中指１.L", "中指２.L", "中指３.L",
        "薬指１.L", "薬指２.L", "薬指３.L",
        "小指１.L", "小指２.L", "小指３.L"
    ],
    'RIGHT': [
        "親指０.R", "親指１.R", "親指２.R",
        "人指１.R", "人指２.R", "人指３.R",
        "中指１.R", "中指２.R", "中指３.R",
        "薬指１.R", "薬指２.R", "薬指３.R",
        "小指１.R", "小指２.R", "小指３.R"
    ]
}

# 获取插件同目录下的json文件路径
def get_gesture_json_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand_gestures.json')

# 从json文件加载手势数据
def load_gesture_data():
    path = get_gesture_json_path()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

# 保存手势数据到json文件
def save_gesture_data(data):
    path = get_gesture_json_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 全局变量缓存手势数据
gesture_data_cache = load_gesture_data()

def get_gesture_data():
    return gesture_data_cache

# 保存并刷新缓存
def update_gesture_data(new_data):
    global gesture_data_cache
    gesture_data_cache = new_data
    save_gesture_data(gesture_data_cache)

def store_bone_data(bone):
    """存储骨骼数据"""
    return {
        'location': list(bone.location),
        'rotation_quaternion': list(bone.rotation_quaternion),
        'scale': list(bone.scale)
    }

def apply_bone_data(bone, data):
    """应用骨骼数据"""
    bone.location = data['location']
    bone.rotation_quaternion = data['rotation_quaternion']
    bone.scale = data['scale']

def flip_pose_data(bones_data, from_side, to_side):
    flipped_data = {}
    for bone_name, data in bones_data.items():
        # 目标骨骼名
        target_name = bone_name.replace('.R', '.L') if from_side == 'RIGHT' else bone_name.replace('.L', '.R')
        loc = Vector(data['location'])
        rot = Quaternion(data['rotation_quaternion'])
        scale = Vector(data['scale'])
        # 位置X轴取反
        flipped_loc = Vector((-loc.x, loc.y, loc.z))
        # 四元数镜像（Blender骨骼对称标准：x和w分量取反）
        flipped_rot = Quaternion((rot.w, -rot.x, -rot.y, rot.z))
        flipped_data[target_name] = {
            'location': list(flipped_loc),
            'rotation_quaternion': list(flipped_rot),
            'scale': list(scale)
        }
    return flipped_data

class GESTURE_OT_record(Operator):
    """记录当前手部动作"""
    bl_idname = "gesture.record"
    bl_label = "记录手势"
    
    gesture_name: StringProperty(
        name="手势名称",
        default="新手势"
    )
    
    hand_side: EnumProperty(
        name="手部",
        items=[
            ('LEFT', "左手", ""),
            ('RIGHT', "右手", "")
        ],
        default='LEFT'
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'ARMATURE'
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "gesture_name")
    
    def execute(self, context):
        # 获取当前帧的手部骨骼数据
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "请选择一个骨架")
            return {'CANCELLED'}
            
        # 确保在姿态模式下
        if armature.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
            
        bones_data = {}
        for bone in armature.pose.bones:
            if bone.name in HAND_BONES[self.hand_side]:
                bones_data[bone.name] = store_bone_data(bone)
        
        # 获取现有数据并更新
        gesture_data = get_gesture_data()
        gesture_data[self.gesture_name] = {
            'hand_side': self.hand_side,
            'bones_data': bones_data
        }
        update_gesture_data(gesture_data)
                
        self.report({'INFO'}, f"已记录手势: {self.gesture_name}")
        return {'FINISHED'}

class GESTURE_OT_apply(Operator):
    """应用已记录的手势"""
    bl_idname = "gesture.apply"
    bl_label = "应用手势"
    
    gesture_name: StringProperty()
    hand_side: EnumProperty(
        name="应用到手部",
        items=[
            ('LEFT', "左手", ""),
            ('RIGHT', "右手", "")
        ],
        default='LEFT'
    )
    
    # 直接注册关键帧，不弹窗
    add_keyframe: BoolProperty(default=True)
    
    def execute(self, context):
        gesture_data = get_gesture_data()
        if self.gesture_name not in gesture_data:
            self.report({'ERROR'}, "手势不存在")
            return {'CANCELLED'}
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "请选择一个骨架")
            return {'CANCELLED'}
        if armature.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        gesture_info = gesture_data[self.gesture_name]
        recorded_hand_side = gesture_info['hand_side']
        bones_data = gesture_info['bones_data']
        if recorded_hand_side == self.hand_side:
            for bone_name, data in bones_data.items():
                if bone_name in armature.pose.bones:
                    bone = armature.pose.bones[bone_name]
                    apply_bone_data(bone, data)
                    bone.bone.select = True
        else:
            flipped_data = flip_pose_data(bones_data, recorded_hand_side, self.hand_side)
            for bone_name, data in flipped_data.items():
                if bone_name in armature.pose.bones:
                    bone = armature.pose.bones[bone_name]
                    apply_bone_data(bone, data)
                    bone.bone.select = True
        # 直接注册关键帧
        for bone in armature.pose.bones:
            if bone.bone.select:
                bone.keyframe_insert(data_path="location", frame=context.scene.frame_current)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=context.scene.frame_current)
                bone.keyframe_insert(data_path="scale", frame=context.scene.frame_current)
        bpy.ops.pose.select_all(action='DESELECT')
        self.report({'INFO'}, f"已应用手势: {self.gesture_name}")
        return {'FINISHED'}

class GESTURE_OT_delete(Operator):
    """删除手势"""
    bl_idname = "gesture.delete"
    bl_label = "删除手势"
    
    gesture_name: StringProperty()
    
    def execute(self, context):
        gesture_data = get_gesture_data()
        if self.gesture_name in gesture_data:
            del gesture_data[self.gesture_name]
            update_gesture_data(gesture_data)
            self.report({'INFO'}, f"已删除手势: {self.gesture_name}")
        return {'FINISHED'}

class GESTURE_PT_main(Panel):
    bl_label = "手势工具"
    bl_idname = "GESTURE_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "手势工具"
    
    def draw(self, context):
        layout = self.layout
        
        # 记录手势部分
        box = layout.box()
        box.label(text="记录手势")
        row = box.row()
        row.operator(GESTURE_OT_record.bl_idname, text="左").hand_side = 'LEFT'
        row.operator(GESTURE_OT_record.bl_idname, text="右").hand_side = 'RIGHT'
        
        # 应用手势部分
        box = layout.box()
        box.label(text="应用手势")
        gesture_data = get_gesture_data()
        for gesture_name in gesture_data.keys():
            row = box.row()
            row.label(text=gesture_name)
            op_left = row.operator(GESTURE_OT_apply.bl_idname, text="左")
            op_left.gesture_name = gesture_name
            op_left.hand_side = 'LEFT'
            op_right = row.operator(GESTURE_OT_apply.bl_idname, text="右")
            op_right.gesture_name = gesture_name
            op_right.hand_side = 'RIGHT'
            row.operator(GESTURE_OT_delete.bl_idname, text="删除", icon='X').gesture_name = gesture_name

classes = (
    GESTURE_OT_record,
    GESTURE_OT_apply,
    GESTURE_OT_delete,
    GESTURE_PT_main,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # 添加场景属性
    bpy.types.Scene.gesture_data = StringProperty(
        name="手势数据",
        default="{}"
    )

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    # 删除场景属性
    del bpy.types.Scene.gesture_data

if __name__ == "__main__":
    register()
