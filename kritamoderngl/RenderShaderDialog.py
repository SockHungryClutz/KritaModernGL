from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import QDialog, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit

# Dialog box for render shader
class RenderShaderDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(RenderShaderDialog, self).__init__(parent)
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
        
        self.vertLayout = QHBoxLayout()
        self.vertLabel = QLabel("Vertex Shader:", self)
        self.vertLabel2 = QLabel("Number of vertices to render:", self)
        self.vertNumber = QLineEdit("-1", self)
        self.vertNumber.setValidator(QIntValidator(-1, 2147483647, self))
        self.vertLayout.addWidget(self.vertLabel2)
        self.vertLayout.addWidget(self.vertNumber)
        self.vertBox = QTextEdit()
        self.vertBox.setAcceptRichText(False)
        self.vertBox.setTabChangesFocus(False)
        self.vertBox.setFont(monoFont)
        
        self.fragLabel = QLabel("Fragment Shader:", self)
        self.fragBox = QTextEdit()
        self.fragBox.setAcceptRichText(False)
        self.fragBox.setTabChangesFocus(False)
        self.fragBox.setFont(monoFont)
        
        self.errLabel = QLabel("Errors:", self)
        self.errBox = QTextEdit()
        self.errBox.setAcceptRichText(False)
        self.errBox.setReadOnly(True)
        self.errBox.setPlaceholderText("Enter shader code above and click Run, warnings and errors will appear here.")
        
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.vertLabel)
        vbox.addLayout(self.vertLayout)
        vbox.addWidget(self.vertBox)
        vbox.addWidget(self.fragLabel)
        vbox.addWidget(self.fragBox)
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
        # Create input texture from current layer
        inputTexture = self.ext.ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorDepth)
        # Create output buffer with canvas size and color info
        outputTexture = self.ext.ctx.texture((doc.width(), doc.height()), components, dtype=colorDepth)
        outFrameBuffer = self.ext.ctx.framebuffer([outputTexture])
        # Create a shader program from the text boxes
        program = self.ext.ctx.program(
            vertex_shader=self.vertBox.toPlainText(),
            fragment_shader=self.fragBox.toPlainText(),
        )
        # Set the texture units for the textures
        outFrameBuffer.use() # Through magic, framebuffers are automatically used as output(?)
        # TODO: test if selected layer is ctually being piped in properly and useable
        inputTexture.use()
        vao = self.ext.ctx.vertex_array(program, [])
        try:
            vertices = int(self.vertNumber.text())
            vao.vertices = vertices
        except ValueError as e:
            # Could not parse number of vertices, good luck
            pass
        
        self.ext.ctx.clear()
        # Display any errors in warningWidget
        try:
            vao.render()
            # Add new buffer to the canvas
            curNode = node.duplicate()
            curNode.setName("Render Result")
            curNode.setPixelData(outputTexture.read(), 0, 0, doc.width(), doc.height())
            node.parentNode().addChildNode(curNode, doc.activeNode())
            doc.refreshProjection()
        except Exception as e:
            self.errBox.setPlainText(str(e))
        # Cleanup
        inputTexture.release()
        outputTexture.release()
        outFrameBuffer.release()
        vao.release()
        program.release()
        self.saveSettings()

    def showHelp(self):
        self.helpWindow.setText("Krita ModernGL Render Shader Programming")
        self.helpWindow.setInformativeText("""This tool is designed for running GLSL vertex and fragment shaders inside of Krita and rendering their output to a new layer in the current document. If you would like to learn more, https://learnopengl.com has good tutorials. Here are some more useful bits of info:

   > No vertices are fed into the vertex shader from the program, you will need to define your own vertices inside the shader to render.
   > Use the text box above the vertex shader to specify how many vertices are to be processed.
   > The render primitive mode is triangles since this is the default.
   > Varyings output from the vertex shader can be used as inputs to the fragment shader.
   > The output of the fragment shader will be rendered to a new layer added above the current selected layer.
   > The current selected layer can be used as a texture input if you use its texture unit.
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
        self.ext.settings.setValue("mgl_vert_number", self.vertNumber.text())
        if self.vertBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_vert_shader", self.vertBox.toPlainText())
        if self.fragBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_frag_shader", self.fragBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        rect = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(rect)
        self.vertNumber.setText(self.ext.settings.value("mgl_vert_number", "-1"))
        self.vertBox.setPlainText(self.ext.settings.value("mgl_vert_shader", ""))
        self.fragBox.setPlainText(self.ext.settings.value("mgl_frag_shader", ""))