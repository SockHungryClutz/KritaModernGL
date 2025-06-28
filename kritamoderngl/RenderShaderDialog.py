from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import QDialog, QFileDialog, QComboBox, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit

# Dialog box for render shader
class RenderShaderDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(RenderShaderDialog, self).__init__(parent)
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
        self.buttonBox.helpRequested.connect(self.showHelp)
        self.buttonBox.rejected.connect(self.saveAndReject)
        self.setWindowModality(Qt.WindowModal)
        monoFont = QFont("Monospace")
        monoFont.setStyleHint(QFont.TypeWriter)
        
        self.vertLayout = QHBoxLayout()
        self.vertLabel = QLabel("Vertex Shader:", self)
        self.vertLabel2 = QLabel("Number of vertices to render:", self)
        self.vertNumber = QLineEdit("-1", self)
        self.vertLabel3 = QLabel("Primitive mode:", self)
        self.vertNumber.setValidator(QIntValidator(-1, 2147483647, self))
        self.vertMode = QComboBox()
        self.vertMode.addItems(
            ["Points",
            "Lines",
            "Line Loop",
            "Line Strip",
            "Triangles",
            "Triangle Strip",
            "Triangle Fan"])
        self.vertLayout.addWidget(self.vertLabel2)
        self.vertLayout.addWidget(self.vertNumber)
        self.vertLayout.addWidget(self.vertLabel3)
        self.vertLayout.addWidget(self.vertMode)
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
        
        # For some reason, the geometry as applied differs from how it should be
        # Save the difference and apply it on save
        self.geometryDelta = QRect(
            self.geometry().x() - self.readGeometry.x(),
            self.geometry().y() - self.readGeometry.y(),
            self.geometry().width() - self.readGeometry.width(),
            self.geometry().height() - self.readGeometry.height())

    def applyChanges(self):
        doc = Krita.instance().activeDocument()
        if not doc:
            self.errBox.setPlainText("You need to have a document open to use this script!")
            return
        newNode = None
        # Get information for the buffer format
        # Number of components is the number of capitals in the color model, unless GRAYA
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
            ## Create input texture from current layer
            inputTexture = ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorDepth)
            ## Create output buffer with canvas size and color info
            outputTexture = ctx.texture((doc.width(), doc.height()), components, dtype=colorDepth)
            outFrameBuffer = ctx.framebuffer([outputTexture])
            ## Create a shader program from the text boxes
            try:
                program = ctx.program(
                    vertex_shader=self.vertBox.toPlainText(),
                    fragment_shader=self.fragBox.toPlainText())
            except Exception as e:
                self.errBox.setPlainText(str(e))
                # Cleanup and early exit
                inputTexture.release()
                outputTexture.release()
                outFrameBuffer.release()
                self.saveSettings()
                return
            # Set the texture units for the textures
            outFrameBuffer.use() # Through magic, framebuffers are automatically used as output
            inputTexture.use() # And textures can be used as input with a sampler2D
            vao = ctx.vertex_array(program, [])
            try:
                vertices = int(self.vertNumber.text())
                if vertices != -1:
                    vao.vertices = vertices
                # Set the primitive drawing mode
                match self.vertMode.currentIndex():
                    case 0:
                        vao.mode = ctx.POINTS
                    case 1:
                        vao.mode = ctx.LINES
                    case 2:
                        vao.mode = ctx.LINE_LOOP
                    case 3:
                        vao.mode = ctx.LINE_STRIP
                    case 4:
                        vao.mode = ctx.TRIANGLES
                    case 5:
                        vao.mode = ctx.TRIANGLE_STRIP
                    case 6:
                        vao.mode = ctx.TRIANGLE_FAN
                    case _:
                        vao.mode = ctx.TRIANGLES
            except ValueError as e:
                # Could not parse number of vertices, good luck
                pass
            
            ctx.clear()
            # Display any errors in warningWidget
            try:
                vao.render()
                ctx.finish()
                # Put the result into a new node
                newNode = doc.createNode("Render Result", "paintlayer")
                newNode.setPixelData(outputTexture.read(), 0, 0, doc.width(), doc.height())
            except Exception as e:
                self.errBox.setPlainText(str(e))
            # Cleanup
            inputTexture.release()
            outputTexture.release()
            outFrameBuffer.release()
            vao.release()
            program.release()
        if newNode:
            # Exit the context scope before adding a new node
            node.parentNode().addChildNode(newNode, node)
            doc.refreshProjection()
        self.saveSettings()

    def showHelp(self):
        self.helpWindow.setText("Krita ModernGL Render Shader Programming")
        self.helpWindow.setInformativeText("""This tool is designed for running GLSL vertex and fragment shaders inside of Krita and rendering their output to a new layer in the current document. If you would like to learn more, https://learnopengl.com has good tutorials. Here are some more useful bits of info:

   > No vertices are fed into the vertex shader from the program, you will need to define your own vertices inside the shader to render.
   > Use the text box above the vertex shader to specify how many vertices are to be processed.
   > Change the primitive draw mode using the selection box next to the box to specify the number of vertices.
   > Varyings output from the vertex shader can be used as inputs to the fragment shader.
   > The output of the fragment shader will be rendered to a new layer added above the current selected layer.
   > The current selected layer can be used as a texture input with uniform sampler2D.
   > There is no syntax highlighting, it is advisable you use some other editor to make the shaders.
   > Shader files can be saved and loaded using Save and Open, selecting a vertex shader first then a fragment shader.""")
        self.helpWindow.exec()

    def openFile(self):
        # Because this has two shaders to save, this will open two different dialogs
        # Open a file selection dialog
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Vertex Shaders (*.vert)")
        # Load the selected shaders into the text boxes
        with open(file[0], 'r') as vf:
            self.vertBox.setPlainText(vf.read())
        # Open a file selection dialog for the next shader
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Fragment Shaders (*.frag)")
        with open(file[0], 'r') as ff:
            self.fragBox.setPlainText(ff.read())

    def saveFile(self):
        # This will also open two dialogs to save the two different shaders
        # Open a file save dialog
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Vertex Shaders (*.vert)")
        # Write the contents of the text box to file
        with open(file[0], 'w') as vf:
            vf.write(self.vertBox.toPlainText())
        # Open a file save dialog for the second shader
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Fragment Shaders (*.frag)")
        with open(file[0], 'w') as ff:
            ff.write(self.fragBox.toPlainText())

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
        self.ext.settings.setValue("mgl_vert_number", self.vertNumber.text())
        self.ext.settings.setValue("mgl_vert_mode", self.vertMode.currentIndex())
        if self.vertBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_vert_shader", self.vertBox.toPlainText())
        if self.fragBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_frag_shader", self.fragBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        self.readGeometry = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(self.readGeometry)
        self.vertNumber.setText(self.ext.settings.value("mgl_vert_number", "-1"))
        self.vertMode.setCurrentIndex(int(self.ext.settings.value("mgl_vert_mode", "4")))
        self.vertBox.setPlainText(self.ext.settings.value("mgl_vert_shader", ""))
        self.fragBox.setPlainText(self.ext.settings.value("mgl_frag_shader", ""))