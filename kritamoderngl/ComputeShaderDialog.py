from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import QDialog, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit

# Dialog box for compute shader
class ComputeShaderDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(ComputeShaderDialog, self).__init__(parent)
        self.ext = extension
        
        self.helpWindow = QMessageBox()
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.addButton("Run", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Help", QDialogButtonBox.HelpRole)
        self.buttonBox.addButton("Close", QDialogButtonBox.RejectRole)
        self.setWindowModality(Qt.WindowModal)
        self.buttonBox.accepted.connect(self.applyChanges)
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
        self.compLayout.addWidget(self.compLabelX)
        self.compLayout.addWidget(self.compWGX)
        self.compLayout.addWidget(self.compLabelY)
        self.compLayout.addWidget(self.compWGY)
        self.compLayout.addWidget(self.compLabelZ)
        self.compLayout.addWidget(self.compWGZ)
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
        self.show()
        self.activateWindow()

    def applyChanges(self):
        doc = Krita.instance().activeDocument()
        if not doc:
            self.errBox.setPlainText("You need to have a document open to use this script!")
            return
        # Get information for the buffer format
        # Number of components is the number of capitals in the color model, unless GRAYA
        doc = Krita.instance().activeDocument()
        node = doc.activeNode()
        colorModel = node.colorModel()
        if colorModel == "GRAYA":
            components = 2
        else:
            components = sum(1 for c in colorModel if c.isupper())
        colorDepth = node.colorDepth()
        colorDepth = colorDepth[0].lower() + str(int(colorDepth[1:]) // 8)
        # Must specify this context otherwise Krita will cause issues if using OpenGL for main renderer
        with self.ext.ctx as ctx:
            # Create input texture from current layer
            inputTexture = ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorDepth)
            # Create output buffer with canvas size and color info
            outputTexture = ctx.texture((doc.width(), doc.height()), components, dtype=colorDepth)
            # Create a shader program from the text boxes
            try:
                shader = ctx.compute_shader(self.compBox.toPlainText())
            except Exception as e:
                self.errBox.setPlainText(str(e))
                # Cleanup and early exit
                inputTexture.release()
                outputTexture.release()
                self.saveSettings()
                return
            # Set the texture units for the textures
            outputTexture.bind_to_image(0, read=True, write=True)
            inputTexture.bind_to_image(1, read=True, write=False)
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
                # Add new buffer to the canvas
                curNode = node.duplicate()
                curNode.setName("Compute Result")
                curNode.setPixelData(outputTexture.read(), 0, 0, doc.width(), doc.height())
                node.parentNode().addChildNode(curNode, doc.activeNode())
                doc.refreshProjection()
            except Exception as e:
                self.errBox.setPlainText(str(e))
            # Cleanup
            inputTexture.release()
            outputTexture.release()
            shader.release()
        self.saveSettings()

    def showHelp(self):
        self.helpWindow.setText("Krita ModernGL Compute Shader Programming")
        self.helpWindow.setInformativeText("""This tool is designed for running GLSL compute shaders inside of Krita and rendering their output to a new layer in the current document. If you would like to learn more, https://www.khronos.org/opengl/wiki/Compute_Shader has essential resources. Here are some more useful bits of info:

   > The output texture is bound to texture unit 0.
   > The input texture is taken from the current selected layer and is bound to texture unit 1.
   > The output will be rendered to a new layer added above the current selected layer.
   > There is no syntax highlighting, it is advisable you use some other editor to make the shaders.""")
        self.helpWindow.exec()

    def saveAndReject(self):
        self.saveSettings()
        self.reject()

    def closeEvent(self, event):
        self.saveSettings()
        event.accept()

    def saveSettings(self):
        rect = self.geometry()
        self.ext.settings.setValue("mgl_geometry", rect)
        self.ext.settings.setValue("mgl_comp_wgx", self.compWGX.text())
        self.ext.settings.setValue("mgl_comp_wgy", self.compWGY.text())
        self.ext.settings.setValue("mgl_comp_wgz", self.compWGZ.text())
        if self.compBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_comp_shader", self.compBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        rect = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(rect)
        self.compWGX.setText(self.ext.settings.value("mgl_comp_wgx", "1"))
        self.compWGY.setText(self.ext.settings.value("mgl_comp_wgy", "1"))
        self.compWGZ.setText(self.ext.settings.value("mgl_comp_wgz", "1"))
        self.compBox.setPlainText(self.ext.settings.value("mgl_comp_shader", ""))