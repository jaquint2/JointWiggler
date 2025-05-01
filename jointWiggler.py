import maya.OpenMayaUI as omui
import maya.cmds as cmds
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance

try:
    from noise import pnoise3
except ImportError:
    def pnoise3(x, y, z, repeat=1024):
        import random
        random.seed(int(x * 100 + y * 10 + z) % repeat)
        return random.uniform(-1.0, 1.0)

def get_maya_main_window():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QMainWindow)

class NoiseVisualizer(QtWidgets.QWidget):
    def __init__(self, get_values_callback, *args, **kwargs):
        super(NoiseVisualizer, self).__init__(*args, **kwargs)
        self.get_values_callback = get_values_callback
        self.setMinimumHeight(120)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(30, 30, 30))

        w, h = self.width(), self.height()
        axes_colors = {'x': QtGui.QColor(200, 50, 50),
                       'y': QtGui.QColor(50, 200, 50),
                       'z': QtGui.QColor(50, 100, 255)}

        seed = self.get_values_callback('seed')
        speed = self.get_values_callback('speed')
        start = self.get_values_callback('start_frame')
        end = self.get_values_callback('end_frame')
        frame_range = max(end - start, 1)

        for axis in ['x', 'y', 'z']:
            if not self.get_values_callback(f"{axis}_enabled"):
                continue
            freq = self.get_values_callback(f"{axis}_freq")
            amp = self.get_values_callback(f"{axis}_amp")
            min_rot = self.get_values_callback(f"{axis}_min")
            max_rot = self.get_values_callback(f"{axis}_max")
            path = QtGui.QPainterPath()
            last_val = None

            for i in range(w):
                t = start + (i / float(w)) * frame_range
                val = pnoise3(t * speed * freq, 0.0, seed)
                norm = (val + 1.0) / 2.0
                y_val = min_rot + (max_rot - min_rot) * norm
                y = h / 2 - y_val * (h / 180) 
                if last_val is None:
                    path.moveTo(i, y)
                else:
                    path.lineTo(i, y)
                last_val = y

            pen = QtGui.QPen(axes_colors[axis], 2)
            painter.setPen(pen)
            painter.drawPath(path)

        painter.end()

class Wiggle3DUI(QtWidgets.QDialog):
    def __init__(self, parent=get_maya_main_window()):
        super(Wiggle3DUI, self).__init__(parent)
        self.setWindowTitle("Joint Wiggler")
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.joints = []
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        chain_layout = QtWidgets.QHBoxLayout()
        self.chain_label = QtWidgets.QLabel("No chain selected")
        pick_btn = QtWidgets.QPushButton("Pick Joint Chain")
        pick_btn.clicked.connect(self.pick_joint_chain)
        chain_layout.addWidget(self.chain_label)
        chain_layout.addWidget(pick_btn)
        layout.addLayout(chain_layout)

        self.seed_spin = QtWidgets.QDoubleSpinBox()
        self.seed_spin.setRange(0, 10000)
        self.seed_spin.setValue(1.0)

        self.speed_spin = QtWidgets.QDoubleSpinBox()
        self.speed_spin.setRange(0.01, 10.0)
        self.speed_spin.setValue(1.0)

        self.start_frame_spin = QtWidgets.QSpinBox()
        self.start_frame_spin.setRange(-10000, 10000)
        self.start_frame_spin.setValue(int(cmds.playbackOptions(q=True, min=True)))

        self.end_frame_spin = QtWidgets.QSpinBox()
        self.end_frame_spin.setRange(-10000, 10000)
        self.end_frame_spin.setValue(int(cmds.playbackOptions(q=True, max=True)))

        layout.addWidget(QtWidgets.QLabel("Seed:"))
        layout.addWidget(self.seed_spin)
        layout.addWidget(QtWidgets.QLabel("Speed:"))
        layout.addWidget(self.speed_spin)
        layout.addWidget(QtWidgets.QLabel("Start Frame:"))
        layout.addWidget(self.start_frame_spin)
        layout.addWidget(QtWidgets.QLabel("End Frame:"))
        layout.addWidget(self.end_frame_spin)

        self.axis_controls = {}
        for axis in ['X', 'Y', 'Z']:
            group = QtWidgets.QGroupBox(f"{axis}-Axis Settings")
            group.setCheckable(True)
            group.setChecked(axis == 'X')
            form = QtWidgets.QFormLayout()

            amp = QtWidgets.QDoubleSpinBox()
            amp.setRange(0, 10)
            amp.setValue(1.0)
            form.addRow("Amplitude:", amp)

            freq = QtWidgets.QDoubleSpinBox()
            freq.setRange(0.1, 10.0)
            freq.setValue(1.0)
            form.addRow("Frequency:", freq)

            min_spin = QtWidgets.QDoubleSpinBox()
            min_spin.setRange(-180, 180)
            min_spin.setValue(-10)
            form.addRow("Min Rotation (°):", min_spin)

            max_spin = QtWidgets.QDoubleSpinBox()
            max_spin.setRange(-180, 180)
            max_spin.setValue(10)
            form.addRow("Max Rotation (°):", max_spin)

            group.setLayout(form)
            layout.addWidget(group)
            self.axis_controls[axis.lower()] = {
                "group": group,
                "amplitude": amp,
                "frequency": freq,
                "min": min_spin,
                "max": max_spin
            }

        self.visualizer = NoiseVisualizer(self.get_value)
        layout.addWidget(QtWidgets.QLabel("Noise Curve Preview:"))
        layout.addWidget(self.visualizer)

        self.seed_spin.valueChanged.connect(self.visualizer.update)
        self.speed_spin.valueChanged.connect(self.visualizer.update)
        self.start_frame_spin.valueChanged.connect(self.visualizer.update)
        self.end_frame_spin.valueChanged.connect(self.visualizer.update)

        for ctrl in self.axis_controls.values():
            ctrl["amplitude"].valueChanged.connect(self.visualizer.update)
            ctrl["frequency"].valueChanged.connect(self.visualizer.update)
            ctrl["min"].valueChanged.connect(self.visualizer.update)
            ctrl["max"].valueChanged.connect(self.visualizer.update)
            ctrl["group"].toggled.connect(self.visualizer.update)

        self.apply_btn = QtWidgets.QPushButton("Apply Wiggle")
        self.apply_btn.clicked.connect(self.apply_wiggle)
        layout.addWidget(self.apply_btn)

    def get_value(self, key):
        if key == 'seed':
            return self.seed_spin.value()
        if key == 'speed':
            return self.speed_spin.value()
        if key == 'start_frame':
            return self.start_frame_spin.value()
        if key == 'end_frame':
            return self.end_frame_spin.value()

        axis = key[0]
        ctrl = self.axis_controls[axis]
        if key.endswith('_enabled'):
            return ctrl['group'].isChecked()
        elif key.endswith('_amp'):
            return ctrl['amplitude'].value()
        elif key.endswith('_freq'):
            return ctrl['frequency'].value()
        elif key.endswith('_min'):
            return ctrl['min'].value()
        elif key.endswith('_max'):
            return ctrl['max'].value()
        return 0

    def pick_joint_chain(self):
        selection = cmds.ls(selection=True, type="joint")
        if not selection:
            cmds.warning("Please select a root joint.")
            return
        root = selection[0]
        self.joints = cmds.listRelatives(root, ad=True, type="joint") or []
        self.joints.append(root)
        self.joints = list(reversed(self.joints))
        self.chain_label.setText(f"Picked {len(self.joints)} joints")

    def apply_wiggle(self):
        if len(self.joints) < 3:
            cmds.warning("Pick a joint chain with at least 3 joints.")
            return

        start_frame = self.get_value("start_frame")
        end_frame = self.get_value("end_frame")
        speed = self.get_value("speed")
        seed = self.get_value("seed")

        cmds.undoInfo(openChunk=True)
        try:
            for i, joint in enumerate(self.joints):
                offset = i * 0.33
                for frame in range(start_frame, end_frame + 1):
                    time = frame / 24.0 * speed
                    for axis in ['x', 'y', 'z']:
                        if not self.get_value(f"{axis}_enabled"):
                            continue
                        freq = self.get_value(f"{axis}_freq")
                        amp = self.get_value(f"{axis}_amp")
                        min_val = self.get_value(f"{axis}_min")
                        max_val = self.get_value(f"{axis}_max")
                        noise_val = pnoise3(time * freq, offset * freq, seed)
                        norm_val = (noise_val + 1.0) / 2.0
                        disp = min_val + (max_val - min_val) * norm_val
                        cmds.setKeyframe(joint, attribute=f"rotate{axis.upper()}", t=frame, value=disp)
        finally:
            cmds.undoInfo(closeChunk=True)

def show_wiggle3d_visualizer():
    for widget in QtWidgets.QApplication.allWidgets():
        if isinstance(widget, Wiggle3DUI):
            widget.close()
    dlg = Wiggle3DUI()
    dlg.show()

show_wiggle3d_visualizer()
