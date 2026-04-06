from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths, QUuid
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import QDialog, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit
from . import ComputeBufferMapperDialog

# Dialog box for compute shader
class ComputeShaderDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(ComputeShaderDialog, self).__init__(parent)
        self.ext = extension
        
        self.helpWindow = QMessageBox()
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Open |
            QDialogButtonBox.Save |
            QDialogButtonBox.Ok |
            QDialogButtonBox.Help |
            QDialogButtonBox.Cancel,
            self)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("Run")
        self.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(self.applyChanges)
        self.buttonBox.button(QDialogButtonBox.Open).clicked.connect(self.openFile)
        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.saveFile)
        self.setWindowModality(Qt.WindowModal)
        self.buttonBox.helpRequested.connect(self.showHelp)
        self.buttonBox.rejected.connect(self.saveAndReject)
        monoFont = QFont("Monospace")
        monoFont.setStyleHint(QFont.TypeWriter)
        
        self.compLabel = QLabel("Compute Shader:", self)
        self.compLayout = QHBoxLayout()
        self.compLabelX = QLabel("Workgroup X:", self)
        self.compWGX = QLineEdit("1", self)
        self.compWGX.setValidator(QIntValidator(1, 2147483647, self))
        self.compLabelY = QLabel("Workgroup Y:", self)
        self.compWGY = QLineEdit("1", self)
        self.compWGY.setValidator(QIntValidator(1, 2147483647, self))
        self.compLabelZ = QLabel("Workgroup Z:", self)
        self.compWGZ = QLineEdit("1", self)
        self.compWGZ.setValidator(QIntValidator(1, 2147483647, self))
        self.mapWindow = ComputeBufferMapperDialog.ComputeBufferMapperDialog(self)
        self.settingSpacer = QLabel("   |   ", self)
        self.mapButton = QPushButton("Map Buffers", self)
        self.mapButton.clicked.connect(self.showMap)
        try:
            self.mapWindow.validateMapping()
        except Exception as e:
            self.mapButton.setIcon(Krita.instance().icon("warning"))
            self.mapButton.setToolTip(f"Errors in configuration mapping, open to resolve\nMost likely, previous configuration referred to a layer that does not exist now\n\n{e.args[0]}")
        self.compLayout.addWidget(self.compLabelX)
        self.compLayout.addWidget(self.compWGX)
        self.compLayout.addWidget(self.compLabelY)
        self.compLayout.addWidget(self.compWGY)
        self.compLayout.addWidget(self.compLabelZ)
        self.compLayout.addWidget(self.compWGZ)
        self.compLayout.addWidget(self.settingSpacer)
        self.compLayout.addWidget(self.mapButton)
        self.compBox = QTextEdit()
        self.compBox.setAcceptRichText(False)
        self.compBox.setTabChangesFocus(False)
        self.compBox.setFont(monoFont)
        
        self.errLabel = QLabel("Errors:", self)
        self.errBox = QTextEdit()
        self.errBox.setAcceptRichText(False)
        self.errBox.setReadOnly(True)
        self.errBox.setPlaceholderText("Enter shader code above and click Run, warnings and errors will appear here.")
        
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.compLabel)
        vbox.addLayout(self.compLayout)
        vbox.addWidget(self.compBox)
        vbox.addWidget(self.errLabel)
        vbox.addWidget(self.errBox)
        vbox.addWidget(self.buttonBox)
        
        self.readSettings()
        
        self.setWindowTitle("OpenGL Shader Programming")
        self.setSizeGripEnabled(True)
        self.installEventFilter(self)
        self.show()
        self.activateWindow()
        
        # For some reason, the geometry as applied differs from how it should be
        # Save the difference and apply it on save
        self.geometryDelta = QRect(
            self.geometry().x() - self.readGeometry.x(),
            self.geometry().y() - self.readGeometry.y(),
            self.geometry().width() - self.readGeometry.width(),
            self.geometry().height() - self.readGeometry.height())

    def eventFilter(self, obj, event):
        # Because QDialog is a widget and not a window (even though it's literally a window),
        # this filter is needed to detect when the window (widget) receives focus
        # because the widget does not receive focus events when the window receives focus
        if event.type() == QEvent.WindowActivate:
            try:
                self.mapWindow.validateMapping()
                self.mapButton.setIcon(QIcon())
                self.mapButton.setToolTip("")
            except Exception as e:
                self.mapButton.setIcon(Krita.instance().icon("warning"))
                self.mapButton.setToolTip(f"Errors in configuration mapping, open to resolve\nMost likely, previous configuration referred to a layer that does not exist now\n\n{e.args[0]}")
            return True
        return super().eventFilter(obj, event)

    def showMap(self):
        # Simple function to show the buffer mapping window
        self.mapWindow.open()

    def applyChanges(self):
        doc = Krita.instance().activeDocument()
        if not doc:
            self.errBox.setPlainText("You need to have a document open to use this script!")
            return
        # Check layer validity before doing anything
        try:
            self.mapWindow.validateMapping()
        except Exception as e:
            self.errBox.setPlainText(f"Layer mapping is invalid, click Map Buffers and fix:\n{e.args[0]}")
            return
        newNodes = []
        textures = []
        shader = None
        # Must specify this context otherwise Krita will cause issues if using OpenGL for main renderer
        with self.ext.ctx as ctx:
            # Create a shader program from the text boxes
            try:
                shader = ctx.compute_shader(self.compBox.toPlainText())
            except Exception as e:
                self.errBox.setPlainText(str(e))
                # Cleanup and early exit
                if shader:
                    shader.release()
                self.saveSettings()
                return
            # Create input and output textures
            for item in self.mapWindow.textureMapItems:
                if item.layerId == "<2>":
                    # Special case for new node
                    # Get color format data from the node
                    components, colorType = self.getColorComponentsAndType(doc)
                    texture = ctx.texture((doc.width(), doc.height()), components, dtype=colorType)
                else:
                    if item.layerId == "<>":
                        # Special case for current node
                        node = doc.activeNode()
                    else:
                        node = doc.nodeByUniqueID(QUuid(item.layerId))
                    # Get color format data from the node
                    components, colorType = self.getColorComponentsAndType(node)
                    texture = ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorType)
                textures.append(texture)
                try:
                    # Set the texture units for the textures
                    # Because compute shaders require OpenGL >= 4.3, we can use convenient and easy methods to bind textures
                    texture.bind_to_image(item.index, read=item.read, write=item.write)
                except Exception as e:
                    self.errBox.setPlainText(str(e))
                    # Cleanup and early exit
                    for i in textures:
                        i.release()
                    shader.release()
                    return
            # Try to get the workgroup dimensions
            try:
                workgroupX = int(self.compWGX.text())
                workgroupY = int(self.compWGY.text())
                workgroupZ = int(self.compWGZ.text())
            except ValueError as e:
                self.errBox.setPlainText("Failed to parse workgroup dimensions:\n" + str(e))
            
            ctx.clear()
            # Display any errors in warningWidget
            try:
                shader.run(workgroupX, workgroupY, workgroupZ)
                ctx.finish()
                # Copy the output pixel data
                for index in range(len(self.mapWindow.textureMapItems)):
                    output = self.mapWindow.textureMapItems[index]
                    if not output.write:
                        continue
                    if output.layerId == "<>":
                        node = doc.activeNode()
                    elif output.layerId == "<2>":
                        node = doc.createNode(f"Render Result {index}", "paintlayer")
                        newNodes.append(node)
                    else:
                        node = doc.nodeByUniqueID(QUuid(output.layerId))
                    node.setPixelData(textures[index].read(), 0, 0, doc.width(), doc.height())
            except Exception as e:
                self.errBox.setPlainText(str(e))
            # Cleanup
            for i in textures:
                i.release()
            shader.release()
        # Exit the context scope before adding new nodes
        for newNode in newNodes:
            doc.activeNode().parentNode().addChildNode(newNode, doc.activeNode())
        doc.refreshProjection()
        self.saveSettings()

    def getColorComponentsAndType(self, node):
        # Helper function to get the number of components and data type from a node
        colorModel = node.colorModel()
        # Number of components is the number of capitals in the color model, unless GRAYA
        if colorModel == "GRAYA":
            components = 2
        else:
            components = sum(1 for c in colorModel if c.isupper())
        colorDepth = node.colorDepth()
        colorDepth = colorDepth[0].lower() + str(int(colorDepth[1:]) // 8)
        return components, colorDepth

    def showHelp(self):
        self.helpWindow.setText("Krita ModernGL Compute Shader Programming")
        self.helpWindow.setInformativeText("""This tool is designed for running GLSL compute shaders inside of Krita and rendering their output to a new layer in the current document. If you would like to learn more, https://www.khronos.org/opengl/wiki/Compute_Shader has essential resources. Here are some more useful bits of info:

   > The three Work Group text boxes control the dimensions for the compute shader.
   > Input and output textures can be configured using the Map Buffers button on top left.
   > By default, the active layer is the input on texture unit 1, and the output uses texture unit 0 and will be added to a new layer above the active layer.
   > There is no syntax highlighting, it is advisable you use some other editor to make the shaders.
   > Shader files can be saved and loaded using Save and Open.""")
        self.helpWindow.exec()

    def openFile(self):
        # Open a file selection dialog
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Compute Shaders (*.comp)")
        if file[0]:
            with open(file[0], 'r') as cf:
                self.compBox.setPlainText(cf.read())

    def saveFile(self):
        # Open a file save dialog
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Compute Shaders (*.comp)")
        # Write the contents of the text box to file
        if file[0]:
            with open(file[0], 'w') as cf:
                cf.write(self.compBox.toPlainText())

    def saveAndReject(self):
        self.saveSettings()
        self.reject()

    def closeEvent(self, event):
        self.saveSettings()
        event.accept()

    def saveSettings(self):
        rect = QRect(
            self.geometry().x() - self.geometryDelta.x(),
            self.geometry().y() - self.geometryDelta.y(),
            self.geometry().width() - self.geometryDelta.width(),
            self.geometry().height() - self.geometryDelta.height())
        self.ext.settings.setValue("mgl_geometry", rect)
        self.ext.settings.setValue("mgl_comp_wgx", self.compWGX.text())
        self.ext.settings.setValue("mgl_comp_wgy", self.compWGY.text())
        self.ext.settings.setValue("mgl_comp_wgz", self.compWGZ.text())
        if self.compBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_comp_shader", self.compBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        self.readGeometry = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(self.readGeometry)
        self.compWGX.setText(self.ext.settings.value("mgl_comp_wgx", "1"))
        self.compWGY.setText(self.ext.settings.value("mgl_comp_wgy", "1"))
        self.compWGZ.setText(self.ext.settings.value("mgl_comp_wgz", "1"))
        self.compBox.setPlainText(self.ext.settings.value("mgl_comp_shader", ""))