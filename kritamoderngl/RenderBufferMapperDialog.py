from krita import *
from PyQt5.QtCore import Qt, QRect, QUuid
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QFileDialog, QDialogButtonBox, QComboBox, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox, QPushButton
import json
from . import TextureMapItem

# Dialog box to configure input and output buffers for the render shader dialog
class RenderBufferMapperDialog(QDialog):
    def __init__(self, parent=None):
        super(RenderBufferMapperDialog, self).__init__(parent)
        self.inputTextureMapItems = []
        self.outputTextureMapItems = []
        
        self.helpWindow = QMessageBox(parent=self)
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Open |
            QDialogButtonBox.Save |
            QDialogButtonBox.Reset |
            QDialogButtonBox.Apply |
            QDialogButtonBox.Help |
            QDialogButtonBox.Cancel,
            self)
        self.buttonBox.button(QDialogButtonBox.Open).clicked.connect(self.openFile)
        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.saveFile)
        self.buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetMap)
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.applyChanges)
        self.buttonBox.helpRequested.connect(self.showHelp)
        self.buttonBox.rejected.connect(self.saveAndReject)
        self.setWindowModality(Qt.WindowModal)
        
        self.inputLabel = QLabel("Input Texture Units:", self)
        self.createLayerLists()
        self.inputMap = QTableWidget(len(self.inputTextureMapItems), 4, self)
        self.inputMap.setHorizontalHeaderLabels(["Texture Unit Index", "Target Layer", "Repeat", "Sampler Name"])
        self.inputMap.setCornerButtonEnabled(False)
        self.inputMap.verticalHeader().setVisible(False)
        inOrderUp = QPushButton(Krita.instance().icon("arrow-up"), "Move Up")
        inOrderUp.clicked.connect(self.moveInRowUp)
        inOrderDown = QPushButton(Krita.instance().icon("arrow-down"), "Move Down")
        inOrderDown.clicked.connect(self.moveInRowDown)
        inListAdd = QPushButton(Krita.instance().icon("list-add"), "Add")
        inListAdd.clicked.connect(self.addInRow)
        inListRemove = QPushButton(Krita.instance().icon("list-remove"), "Remove")
        inListRemove.clicked.connect(self.removeInRow)
        self.inMapEditBox = QHBoxLayout()
        self.inMapEditBox.addWidget(inOrderUp)
        self.inMapEditBox.addWidget(inOrderDown)
        self.inMapEditBox.addWidget(inListAdd)
        self.inMapEditBox.addWidget(inListRemove)
        
        self.outputLabel = QLabel("Output Frame Buffer:", self)
        self.outputMap = QTableWidget(len(self.outputTextureMapItems), 3, self)
        self.outputMap.setHorizontalHeaderLabels(["Frame Buffer Index", "Target Layer", "Repeat"])
        self.outputMap.setCornerButtonEnabled(False)
        self.outputMap.verticalHeader().setVisible(False)
        outOrderUp = QPushButton(Krita.instance().icon("arrow-up"), "Move Up")
        outOrderUp.clicked.connect(self.moveOutRowUp)
        outOrderDown = QPushButton(Krita.instance().icon("arrow-down"), "Move Down")
        outOrderDown.clicked.connect(self.moveOutRowDown)
        outListAdd = QPushButton(Krita.instance().icon("list-add"), "Add")
        outListAdd.clicked.connect(self.addOutRow)
        outListRemove = QPushButton(Krita.instance().icon("list-remove"), "Remove")
        outListRemove.clicked.connect(self.removeOutRow)
        self.outMapEditBox = QHBoxLayout()
        self.outMapEditBox.addWidget(outOrderUp)
        self.outMapEditBox.addWidget(outOrderDown)
        self.outMapEditBox.addWidget(outListAdd)
        self.outMapEditBox.addWidget(outListRemove)
        self.readSettings()
        
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.inputLabel)
        vbox.addWidget(self.inputMap)
        vbox.addLayout(self.inMapEditBox)
        vbox.addWidget(self.outputLabel)
        vbox.addWidget(self.outputMap)
        vbox.addLayout(self.outMapEditBox)
        vbox.addWidget(self.buttonBox)
        
        self.setWindowTitle("Configure Input and Output Buffers")
        self.setSizeGripEnabled(False)

    def showEvent(self, event):
        # This will undo any changes from last time the window was shown and update the layer list drop down
        self.createLayerLists()
        self.readSettings()

    def updateAllViews(self):
        # This will update both the input and output UI
        self.updateInView()
        self.updateOutView()

    def updateInView(self):
        # Updates the input mapping UI to reflect changes made to the data models
        monoFont = QFont("Monospace")
        monoFont.setStyleHint(QFont.TypeWriter)
        self.inputMap.setRowCount(len(self.inputTextureMapItems))
        for idx in range(len(self.inputTextureMapItems)):
            # Create the widgets and items that will populate the cells
            indexWidget = QTableWidgetItem(str(idx))
            indexWidget.setFlags(indexWidget.flags() ^ Qt.ItemIsEditable)
            indexWidget.setToolTip("Texture Unit Index.\nThis must be in order, change by reordering rows.")
            layerWidget = QComboBox()
            layerWidget.addItems(["", "<ACTIVE LAYER>"] + self.nameList)
            layerWidget.setInsertPolicy(QComboBox.NoInsert)
            layerWidget.setToolTip("Choose layer in current document to sample from.\n<ACTIVE LAYER> will sample the currently selected layer.")
            try:
                layerWidget.setCurrentIndex(self.uuidList.index(self.inputTextureMapItems[idx].layerId))
            except ValueError:
                layerWidget.setCurrentIndex(0)
            repeatWidget = QCheckBox()
            repeatWidget.setChecked(self.inputTextureMapItems[idx].repeat)
            repeatWidget.setToolTip("Set whether the texture repeats when sampling beyond the bounds.")
            samplerWidget = QTableWidgetItem()
            samplerWidget.setFont(monoFont)
            samplerWidget.setToolTip("Set the name of the sampler to map to in the fragment shader.")
            if self.inputTextureMapItems[idx].variableName: samplerWidget.setText(self.inputTextureMapItems[idx].variableName)
            # Assign the widgets to cells
            self.inputMap.setItem(idx, 0, indexWidget)
            self.inputMap.setCellWidget(idx, 1, layerWidget)
            self.inputMap.setCellWidget(idx, 2, repeatWidget)
            self.inputMap.setItem(idx, 3, samplerWidget)
    
    def updateOutView(self):
        # Updates the output mapping UI to reflect changes made to the data models
        self.outputMap.setRowCount(len(self.outputTextureMapItems))
        for idx in range(len(self.outputTextureMapItems)):
            # Create the widgets and items that will populate the cells
            indexWidget = QTableWidgetItem(str(idx))
            indexWidget.setFlags(indexWidget.flags() ^ Qt.ItemIsEditable)
            indexWidget.setToolTip("Frame Buffer Index.\nThis must be in order, change by reordering rows.")
            layerWidget = QComboBox()
            layerWidget.addItems(["", "<NEW LAYER>"] + self.nameList)
            layerWidget.setInsertPolicy(QComboBox.NoInsert)
            layerWidget.setToolTip("Choose layer in current document to sample from.\n<NEW LAYER> will add a new layer above the currently selected layer.")
            try:
                layerWidget.setCurrentIndex(self.uuidList.index(self.outputTextureMapItems[idx].layerId))
            except ValueError:
                layerWidget.setCurrentIndex(0)
            repeatWidget = QCheckBox()
            repeatWidget.setChecked(self.outputTextureMapItems[idx].repeat)
            repeatWidget.setToolTip("Set whether the texture repeats when sampling beyond the bounds.")
            # Assign the widgets to cells
            self.outputMap.setItem(idx, 0, indexWidget)
            self.outputMap.setCellWidget(idx, 1, layerWidget)
            self.outputMap.setCellWidget(idx, 2, repeatWidget)
    
    def updateAllModels(self):
        # Will update both the input and output list models
        self.updateInModel()
        self.updateOutModel()

    def updateInModel(self):
        # Updates the input list data to reflect changes made in the UI view
        self.inputTextureMapItems = []
        for idx in range(self.inputMap.rowCount()):
            mapItem = TextureMapItem.TextureMapItem(self.uuidList[self.inputMap.cellWidget(idx, 1).currentIndex()],
                                                    True,
                                                    False,
                                                    idx,
                                                    self.inputMap.cellWidget(idx, 2).isChecked(),
                                                    self.inputMap.item(idx, 3).text())
            self.inputTextureMapItems.append(mapItem)

    def updateOutModel(self):
        # Updates the output list data to reflect changes made in the UI view
        self.outputTextureMapItems = []
        for idx in range(self.outputMap.rowCount()):
            mapItem = TextureMapItem.TextureMapItem(self.uuidList[self.outputMap.cellWidget(idx, 1).currentIndex()],
                                                    False,
                                                    True,
                                                    idx,
                                                    self.outputMap.cellWidget(idx, 2).isChecked(),
                                                    "")
            self.outputTextureMapItems.append(mapItem)

    def validateMapping(self):
        # Checks if the mapping is valid, throws an exception with description if invalid, nothing otherwise
        self.updateAllModels()
        for item in self.inputTextureMapItems + self.outputTextureMapItems:
            # All inputs and outputs need a valid target layer
            if item.layerId == "":
                raise Exception(f"Invalid Configuration\n{'Input' if item.read else 'Output'} at index {item.index}\nTarget Layer cannot be null.")
            # All Outputs must map to a paintlayer node
            if item.write and item.layerId != "<>":
                layerType = Krita.instance().activeDocument().nodeByUniqueID(QUuid(item.layerId)).type()
                if layerType != "paintlayer" and layerType[-4:] != "mask":
                    raise Exception(f"Invalid Configuration\nOutput at index {item.index}\nTarget Layer is not paintable (type={layerType})")
        return True

    def getSelectedRows(self, table, reverse=False):
        # Helper function to get the currently selected rows on the input buffer table
        # Find which cells are selected and get their rows
        selectedRows = []
        for idx in table.selectedIndexes():
            if idx.row() not in selectedRows:
                selectedRows.append(idx.row())
        selectedRows.sort(reverse=reverse)
        return selectedRows

    def moveInRowUp(self):
        # Move the current selected rows up if able
        # Ensure the model is currently up-to-date
        self.updateInModel()
        selectedRows = self.getSelectedRows(self.inputMap)
        # Row 0 cannot be moved up, so it and any rows in sequence after are invalid and skipped
        invalidRow = 0
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow += 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows up one position from front to back
        for row in selectedRows:
            self.inputTextureMapItems = self.inputTextureMapItems[:row-1] \
                                        + [self.inputTextureMapItems[row]] \
                                        + [self.inputTextureMapItems[row-1]] \
                                        + self.inputTextureMapItems[row+1:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.inputTextureMapItems)):
            self.inputTextureMapItems[idx].index = idx
        # Update view for input map
        self.updateInView()
    
    def moveInRowDown(self):
        # Move the current selected rows down if able
        # Ensure the model is currently up-to-date
        self.updateInModel()
        selectedRows = self.getSelectedRows(self.inputMap, reverse=True)
        # Last row cannot be moved down, so it and any rows in sequence before are invalid and skipped
        invalidRow = len(self.inputTextureMapItems) - 1
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow -= 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows down one position from back to front
        for row in selectedRows:
            self.inputTextureMapItems = self.inputTextureMapItems[:row] \
                                        + [self.inputTextureMapItems[row+1]] \
                                        + [self.inputTextureMapItems[row]] \
                                        + self.inputTextureMapItems[row+2:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.inputTextureMapItems)):
            self.inputTextureMapItems[idx].index = idx
        # Update view for input map
        self.updateInView()
    
    def addInRow(self):
        # Add a new row with default values below the current row, or at the bottom if none are selected
        # Ensure the model is currently up-to-date
        self.updateInModel()
        # If multiple rows are selected, place a new entry below the lowest selected row
        selectedRows = self.getSelectedRows(self.inputMap, reverse=True)
        newEntry = TextureMapItem.TextureMapItem("<>")
        if selectedRows:
            self.inputTextureMapItems.insert(selectedRows[0]+1, newEntry)
        else:
            self.inputTextureMapItems.append(newEntry)
        self.updateInView()
    
    def removeInRow(self):
        # Remove the current selected rows from the table
        # Ensure the model is currently up-to-date
        self.updateInModel()
        # Removing is easy working back to front
        selectedRows = self.getSelectedRows(self.inputMap, reverse=True)
        for row in selectedRows:
            del self.inputTextureMapItems[row]
        self.updateInView()

    def moveOutRowUp(self):
        # Move the current selected rows up if able
        # Ensure the model is currently up-to-date
        self.updateOutModel()
        selectedRows = self.getSelectedRows(self.outputMap)
        # Row 0 cannot be moved up, so it and any rows in sequence after are invalid and skipped
        invalidRow = 0
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow += 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows up one position from front to back
        for row in selectedRows:
            self.outputTextureMapItems = self.outputTextureMapItems[:row-1] \
                                        + [self.outputTextureMapItems[row]] \
                                        + [self.outputTextureMapItems[row-1]] \
                                        + self.outputTextureMapItems[row+1:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.outputTextureMapItems)):
            self.outputTextureMapItems[idx].index = idx
        # Update view for output map
        self.updateOutView()
    
    def moveOutRowDown(self):
        # Move the current selected rows down if able
        # Ensure the model is currently up-to-date
        self.updateOutModel()
        selectedRows = self.getSelectedRows(self.outputMap, reverse=True)
        # Last row cannot be moved down, so it and any rows in sequence before are invalid and skipped
        invalidRow = len(self.outputTextureMapItems) - 1
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow -= 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows down one position from back to front
        for row in selectedRows:
            self.outputTextureMapItems = self.outputTextureMapItems[:row] \
                                        + [self.outputTextureMapItems[row+1]] \
                                        + [self.outputTextureMapItems[row]] \
                                        + self.outputTextureMapItems[row+2:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.outputTextureMapItems)):
            self.outputTextureMapItems[idx].index = idx
        # Update view for output map
        self.updateOutView()
    
    def addOutRow(self):
        # Add a new row with default values below the current row, or at the bottom if none are selected
        # Ensure the model is currently up-to-date
        self.updateOutModel()
        # If multiple rows are selected, place a new entry below the lowest selected row
        selectedRows = self.getSelectedRows(self.outputMap, reverse=True)
        newEntry = TextureMapItem.TextureMapItem("<>",False,True)
        if selectedRows:
            self.outputTextureMapItems.insert(selectedRows[0]+1, newEntry)
        else:
            self.outputTextureMapItems.append(newEntry)
        self.updateOutView()
    
    def removeOutRow(self):
        # Remove the current selected rows from the table
        # Ensure the model is currently up-to-date
        self.updateOutModel()
        # Removing is easy working back to front
        selectedRows = self.getSelectedRows(self.outputMap, reverse=True)
        for row in selectedRows:
            del self.outputTextureMapItems[row]
        self.updateOutView()

    def resetMap(self):
        self.inputTextureMapItems = [TextureMapItem.TextureMapItem("<>")]
        self.outputTextureMapItems = [TextureMapItem.TextureMapItem("<>",False,True)]
        self.updateAllViews()

    def applyChanges(self):
        try:
            self.validateMapping()
            self.saveSettings()
            self.accept()
        except Exception as e:
            self.helpWindow.setText("Configuration Warning")
            self.helpWindow.setInformativeText(e.args[0])
            self.helpWindow.open()

    def showHelp(self):
        self.helpWindow.setText("Texture Unit and Frame Buffer Mapping")
        self.helpWindow.setInformativeText("""This window is for manually mapping texture units for texture inputs and mapping the frame buffer for texture outputs.

   > If the Sampler Name is not set in the input field, OpenGL will try to automatically assign the texture units to samplers, which may have unintended results.
   > If Sampler Name is set, it must match the variable used for the sampler corresponding to the texture unit in the fragment shader.
   > The output frame buffer must be mapped in the fragment shader using `layout(location = <index>)`.
   > All inputs and outputs must be set to a valid layer in the document, outputs must be assigned to a paintlayer or mask layer.
   > The Repeat option sets whether the layer used as the texture will repeat when sampling beyond the texture bounds.
   > Press Reset at any time to reset the inputs and outputs to default values.
   > If you like to poke around, the configuration is saved as JSON. If you break something, delete the mgl_map_texture_map entry in krita-scripterrc and restart Krita.""")
        self.helpWindow.open()

    def openFile(self):
        # Open a file selection dialog
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "JSON File (*.json)")
        if file[0]:
            with open(file[0], 'r') as f:
                jsonMap = json.loads(f.read())
                self.inputTextureMapItems = []
                self.outputTextureMapItems = []
                for item in jsonMap:
                    if item["read"]:
                        self.inputTextureMapItems.append(TextureMapItem.TextureMapItem(json=item))
                    if item["write"]:
                        self.outputTextureMapItems.append(TextureMapItem.TextureMapItem(json=item))
                self.updateAllViews()

    def saveFile(self):
        # Open a file save dialog
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "JSON File (*.json)")
        if file[0]:
            with open(file[0], 'w') as f:
                self.updateAllModels()
                f.write(str(self.inputTextureMapItems + self.outputTextureMapItems))

    def saveAndReject(self):
        self.saveSettings(False)
        self.reject()

    def closeEvent(self, event):
        self.saveSettings(False)
        event.accept()

    def saveSettings(self, saveMaps=True):
        if saveMaps:
            self.updateAllModels()
        rect = QRect(
            self.geometry().x(),
            self.geometry().y(),
            1, 1) # width and height do not matter
        self.parentWidget().ext.settings.setValue("mgl_map_geometry", rect)
        if saveMaps:
            self.parentWidget().ext.settings.setValue("mgl_map_texture_map", str(self.inputTextureMapItems + self.outputTextureMapItems))
        self.parentWidget().ext.settings.sync()

    def readSettings(self):
        readGeometry = self.parentWidget().ext.settings.value("mgl_map_geometry")
        if readGeometry != None:
            # TODO: figure out why the box keeps moving around? Does it?
            self.move(readGeometry.x(), readGeometry.y())
        default = '[{"layerId":"<>","read":true,"write":false,"index":0,"repeat":true,"variableName":""},{"layerId":"<>","read":false,"write":true,"index":0,"repeat":true,"variableName":""}]'
        jsonMap = json.loads(self.parentWidget().ext.settings.value("mgl_map_texture_map", default))
        self.inputTextureMapItems = []
        self.outputTextureMapItems = []
        for item in jsonMap:
            if item["read"]:
                self.inputTextureMapItems.append(TextureMapItem.TextureMapItem(json=item))
            if item["write"]:
                self.outputTextureMapItems.append(TextureMapItem.TextureMapItem(json=item))
        self.updateAllViews()

    def createLayerLists(self):
        # Assume this will work because you need an active document to open the shader plugin
        nodes = Krita.instance().activeDocument().topLevelNodes()
        nameList = []
        uuidList = []
        for node in nodes:
            name, uuid = listNodesRecursive(nameList, uuidList, node)
            nameList.insert(0, name)
            uuidList.insert(0, uuid)
        self.nameList = nameList
        self.uuidList = ["", "<>"] + uuidList

# Helper function to recursively list all nodes in the document
def listNodesRecursive(names, uuids, node, prefix="  "):
    children = node.childNodes()
    for child in children:
        name, uuid = listNodesRecursive(names, uuids, child, "  " + prefix)
        names.insert(0, prefix + name)
        uuids.insert(0, prefix + uuid)
    return node.name(), node.uniqueId().toString()