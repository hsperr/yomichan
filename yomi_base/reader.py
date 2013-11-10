# -*- coding: utf-8 -*-

# Copyright (C) 2013  Alex Yatskov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from PyQt4 import QtGui, QtCore
from about import DialogAbout
from gen import reader_ui
from preferences import DialogPreferences
import constants
import os
import reader_util
import tarfile
import update


class MainWindowReader(QtGui.QMainWindow, reader_ui.Ui_MainWindowReader):
    class State:
        def __init__(self):
            self.filename = unicode()
            self.definitions = list()
            self.searchPosition = 0
            self.searchText = unicode()
            self.scanPosition = 0
            self.archiveIndex = None


    def __init__(self, parent, preferences, language, filename=None, anki=None, closed=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)

        self.textContent.mouseMoveEvent = self.onContentMouseMove
        self.textContent.mousePressEvent = self.onContentMousePress
        self.dockAnki.setEnabled(bool(anki))

        self.preferences = preferences
        self.updateFinder = update.UpdateFinder()
        self.state = self.State()
        self.language = language
        self.addedFacts = list()
        self.anki = anki
        self.closed = closed
        self.zoom = 0

        self.applyPreferences()
        self.updateRecentFiles()
        self.updateDefinitions()

        if filename:
            self.openFile(filename)
        elif self.preferences['loadRecentFile']:
            filenames = self.preferences.recentFiles()
            if len(filenames) > 0:
                self.openFile(filenames[0])

        self.actionOpen.triggered.connect(self.onActionOpen)
        self.actionPreferences.triggered.connect(self.onActionPreferences)
        self.actionAbout.triggered.connect(self.onActionAbout)
        self.actionZoomIn.triggered.connect(self.onActionZoomIn)
        self.actionZoomOut.triggered.connect(self.onActionZoomOut)
        self.actionZoomReset.triggered.connect(self.onActionZoomReset)
        self.actionFind.triggered.connect(self.onActionFind)
        self.actionFindNext.triggered.connect(self.onActionFindNext)
        self.actionToggleWrap.toggled.connect(self.onActionToggleWrap)
        self.actionCopyDefinition.triggered.connect(self.onActionCopyDefinition)
        self.actionCopyAllDefinitions.triggered.connect(self.onActionCopyAllDefinitions)
        self.actionCopySentence.triggered.connect(self.onActionCopySentence)
        self.actionHomepage.triggered.connect(self.onActionHomepage)
        self.actionFeedback.triggered.connect(self.onActionFeedback)
        self.textDefinitions.anchorClicked.connect(self.onDefinitionsAnchorClicked)
        self.textVocabSearch.returnPressed.connect(self.onDefinitionSearchReturn)
        self.listDefinitions.itemDoubleClicked.connect(self.onDefinitionDoubleClicked)
        self.dockVocab.visibilityChanged.connect(self.onVisibilityChanged)
        self.dockKanji.visibilityChanged.connect(self.onVisibilityChanged)
        self.dockAnki.visibilityChanged.connect(self.onVisibilityChanged)
        self.updateFinder.updateResult.connect(self.onUpdaterSearchResult)

        if self.preferences['checkForUpdates']:
            self.updateFinder.start()


    def applyPreferences(self):
        if self.preferences['windowState'] is not None:
            self.restoreState(QtCore.QByteArray.fromBase64(self.preferences['windowState']))
        if self.preferences['windowPosition'] is not None:
            self.move(QtCore.QPoint(*self.preferences['windowPosition']))
        if self.preferences['windowSize'] is not None:
            self.resize(QtCore.QSize(*self.preferences['windowSize']))

        self.comboTags.addItems(self.preferences['tags'])
        self.applyPreferencesContent()


    def applyPreferencesContent(self):
        palette = self.textContent.palette()
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(self.preferences['bgColor']))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(self.preferences['fgColor']))
        self.textContent.setPalette(palette)

        font = self.textContent.font()
        font.setFamily(self.preferences['fontFamily'])
        font.setPointSize(self.preferences['fontSize'] + self.zoom)
        self.textContent.setLineWrapMode(self.preferences['wordWrap'])
        self.textContent.setFont(font)

        self.actionToggleWrap.setChecked(self.preferences['wordWrap'])


    def closeEvent(self, event):
        self.closeFile()
        self.preferences['windowState'] = str(self.saveState().toBase64())
        self.preferences.save()

        if self.anki is not None:
            self.anki.stopEditing()

        if self.closed is not None:
            self.closed()


    def keyPressEvent(self, event):
        visible = self.dockVocab.isVisible() or self.dockKanji.isVisible()
        if visible and event.key() == QtCore.Qt.Key_Shift:
            self.updateSampleFromPosition()


    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()


    def dropEvent(self, event):
        url = event.mimeData().urls()[0]
        self.openFile(url.toLocalFile())


    def moveEvent(self, event):
        self.preferences['windowPosition'] = event.pos().x(), event.pos().y()


    def resizeEvent(self, event):
        self.preferences['windowSize'] = event.size().width(), event.size().height()


    def onActionOpen(self):
        filename = QtGui.QFileDialog.getOpenFileName(
            parent=self,
            caption='Select a file to open',
            filter='Text files (*.txt);;Archive files (*.bz2 *.gz *.tar *.tgz);;All files (*.*)'
        )
        if filename:
            self.openFile(filename)


    def onActionPreferences(self):
        dialog = DialogPreferences(self, self.preferences, self.anki)
        if dialog.exec_() == QtGui.QDialog.Accepted:
            self.applyPreferencesContent()


    def onActionAbout(self):
        dialog = DialogAbout(self)
        dialog.exec_()


    def onActionZoomIn(self):
        font = self.textContent.font()
        if font.pointSize() < 72:
            font.setPointSize(font.pointSize() + 1)
            self.textContent.setFont(font)
            self.zoom += 1


    def onActionZoomOut(self):
        font = self.textContent.font()
        if font.pointSize() > 1:
            font.setPointSize(font.pointSize() - 1)
            self.textContent.setFont(font)
            self.zoom -= 1


    def onActionZoomReset(self):
        if self.zoom:
            font = self.textContent.font()
            font.setPointSize(font.pointSize() - self.zoom)
            self.textContent.setFont(font)
            self.zoom = 0


    def onActionFind(self):
        searchText = self.state.searchText

        cursor = self.textContent.textCursor()
        if cursor.hasSelection():
            searchText = cursor.selectedText()

        searchText, ok = QtGui.QInputDialog.getText(self, 'Find', 'Search text:', text=searchText)
        if searchText and ok:
            self.findText(searchText)


    def onActionFindNext(self):
        if self.state.searchText:
            self.findText(self.state.searchText)


    def onActionToggleWrap(self, wrap):
        mode = QtGui.QPlainTextEdit.WidgetWidth if wrap else QtGui.QPlainTextEdit.NoWrap
        self.preferences['wordWrap'] = wrap
        self.textContent.setLineWrapMode(wrap)


    def onActionCopyDefinition(self):
        reader_util.copyDefinitions(self.state.definitions[:1])


    def onActionCopyAllDefinitions(self):
        reader_util.copyDefinitions(self.state.definitions)


    def onActionCopySentence(self):
        content = unicode(self.textContent.toPlainText())
        sentence = reader_util.findSentence(content, self.state.scanPosition)
        QtGui.QApplication.clipboard().setText(sentence)


    def onActionHomepage(self):
        url = QtCore.QUrl(constants.c['urlHomepage'])
        QtGui.QDesktopServices().openUrl(url)


    def onActionFeedback(self):
        url = QtCore.QUrl(constants.c['urlFeedback'])
        QtGui.QDesktopServices().openUrl(url)


    def onDefinitionsAnchorClicked(self, url):
        command, index = unicode(url.toString()).split(':')
        definition = self.state.definitions[int(index)]

        if command == 'addExpression':
            markup = reader_util.buildFactMarkupExpression(
                definition['expression'],
                definition['reading'],
                definition['glossary'],
                definition['sentence']
            )
            self.ankiAddFact('vocab', markup)
        if command == 'addReading':
            markup = reader_util.buildFactMarkupReading(
                definition['reading'],
                definition['glossary'],
                definition['sentence']
            )
            self.ankiAddFact('vocab', markup)
        elif command == 'copyDefinition':
            reader_util.copyDefinitions([definition])


    def onDefinitionSearchReturn(self):
        text = unicode(self.textVocabSearch.text())
        self.state.definitions, length = self.language.findTerm(text, True)
        self.updateDefinitions()


    def onDefinitionDoubleClicked(self, item):
        if self.anki is not None:
            row = self.listDefinitions.row(item)
            self.anki.browseNote(self.addedFacts[row])


    def onVisibilityChanged(self, visible):
        self.actionToggleAnki.setChecked(self.dockAnki.isVisible())
        self.actionToggleVocab.setChecked(self.dockVocab.isVisible())
        self.actionToggleKanji.setChecked(self.dockKanji.isVisible())


    def onUpdaterSearchResult(self, result):
        if result and unicode(result) > constants.c['appVersion']:
            QtGui.QMessageBox.information(
                self,
                'Yomichan',
                'A new version of Yomichan is available for download!\n\nYou can download this update ({0} > {1}) ' \
                'from "Shared Plugins" in Anki or directly from the Yomichan homepage.'.format(constants.c['appVersion'], result)
            )


    def onContentMouseMove(self, event):
        QtGui.QPlainTextEdit.mouseMoveEvent(self.textContent, event)
        self.updateSampleMouseEvent(event)


    def onContentMousePress(self, event):
        QtGui.QPlainTextEdit.mousePressEvent(self.textContent, event)
        self.updateSampleMouseEvent(event)


    def openFile(self, filename):
        filename = unicode(filename)
        try:
            content = self.openFileByExtension(filename)
        except IOError:
            self.setStatus(u'Failed to load file {0}'.format(filename))
            QtGui.QMessageBox.critical(self, 'Yomichan', 'Cannot open file for read')
            return

        self.closeFile()

        self.state.filename = filename
        self.state.scanPosition = self.preferences.filePosition(filename)
        if self.state.scanPosition > len(content):
            self.state.scanPosition = 0

        self.updateRecentFile()
        self.updateRecentFiles()

        content, encoding = reader_util.decodeContent(content)
        if self.preferences['stripReadings']:
            content = reader_util.stripContentReadings(content)

        self.textContent.setPlainText(content)
        if self.state.scanPosition > 0:
            cursor = self.textContent.textCursor()
            cursor.setPosition(self.state.scanPosition)
            self.textContent.setTextCursor(cursor)
            self.textContent.centerCursor()

        self.setStatus(u'Loaded file {0}'.format(filename))
        self.setWindowTitle(u'Yomichan - {0} ({1})'.format(os.path.basename(filename), encoding))


    def openFileByExtension(self, filename):
        self.clearArchiveFiles()

        if tarfile.is_tarfile(filename):
            with tarfile.open(filename, 'r:*') as tp:
                files = [f for f in tp.getnames() if tp.getmember(f).isfile()]
                names = [f.decode('utf-8') for f in files]

                self.updateArchiveFiles(filename, names)

                content = unicode()
                if len(files) == 1:
                    fp = tp.extractfile(files[0])
                    content = fp.read()
                    fp.close()
                elif len(files) > 1:
                    index, ok = self.selectFileName(names)
                    if ok:
                        fp = tp.extractfile(files[index])
                        content = fp.read()
                        fp.close()
                        self.state.archiveIndex = index
        else:
            self.state.archiveIndex = None
            with open(filename, 'rb') as fp:
                content = fp.read()

        return content


    def selectFileName(self, names):
        if self.state.archiveIndex is not None:
            return self.state.archiveIndex, True

        item, ok = QtGui.QInputDialog.getItem(
            self,
            'Yomichan',
            'Select file to open:',
            self.formatQStringList(names),
            current = 0,
            editable=False
        )

        index, success = self.getItemIndex(item)
        return index - 1, ok and success


    def getItemIndex(self, item):
        return item.split('.').first().toInt()


    def formatQStringList(self, list):
        return [self.formatQString(i, x) for i, x in enumerate(list)]


    def formatQString(self, index, item):
        return QtCore.QString(str(index + 1) + '. ').append(QtCore.QString(item))


    def closeFile(self):
        self.setWindowTitle('Yomichan')
        self.textContent.setPlainText(unicode())
        self.updateRecentFile(False)
        self.state = self.State()


    def findText(self, text):
        content = self.textContent.toPlainText()
        index = content.indexOf(text, self.state.searchPosition)

        if index == -1:
            wrap = self.state.searchPosition != 0
            self.state.searchPosition = 0
            if wrap:
                self.findText(text)
            else:
                QtGui.QMessageBox.information(self, 'Yomichan', 'Search text not found')
        else:
            self.state.searchPosition = index + len(text)
            cursor = self.textContent.textCursor()
            cursor.setPosition(index, QtGui.QTextCursor.MoveAnchor)
            cursor.setPosition(self.state.searchPosition, QtGui.QTextCursor.KeepAnchor)
            self.textContent.setTextCursor(cursor)

        self.state.searchText = text


    def ankiAddFact(self, profile, markup):
        if self.anki is None:
            return False

        profile = self.preferences["profiles"].get(profile)
        if profile is None:
            return False

        fields = reader_util.replaceMarkupInFields(profile['fields'], markup)
        tagsSplit = reader_util.splitTags(unicode(self.comboTags.currentText()))
        tagsJoined = ' '.join(tagsSplit)

        tagIndex = self.comboTags.findText(tagsJoined)
        if tagIndex > 0:
            self.comboTags.removeItem(tagIndex)
        if tagIndex != 0:
            self.comboTags.insertItem(0, tagsJoined)
        self.preferences.updateFactTags(tagsJoined)

        factId = self.anki.addNote(profile['deck'], profile['model'], fields, tagsSplit)
        if factId is None:
            return False

        if markup['reading']:
            summary = u'{expression} [{reading}]'.format(**markup)
        else:
            summary = markup['expression']

        self.addedFacts.append(factId)
        self.listDefinitions.addItem(summary)
        self.listDefinitions.setCurrentRow(self.listDefinitions.count() - 1)
        self.setStatus(u'Added expression {0}; {1} new fact(s) total'.format(markup['expression'], len(self.addedFacts)))

        self.updateDefinitions()
        return True


    def ankiIsFactValid(self, profile, markup):
        if self.anki is None:
            return False

        profile = self.preferences["profiles"].get(profile)
        if profile is None:
            return False

        fields = reader_util.replaceMarkupInFields(profile['fields'], markup)
        return self.anki.canAddNote(profile['deck'], profile['model'], fields)


    def updateSampleMouseEvent(self, event):
        cursor = self.textContent.cursorForPosition(event.pos())
        self.state.scanPosition = cursor.position()
        requested = event.buttons() & QtCore.Qt.MidButton or event.modifiers() & QtCore.Qt.ShiftModifier
        visible = self.dockVocab.isVisible() or self.dockKanji.isVisible()
        if visible and requested:
            self.updateSampleFromPosition()


    def updateSampleFromPosition(self):
        samplePosStart = self.state.scanPosition
        samplePosEnd = self.state.scanPosition + self.preferences['scanLength']

        cursor = self.textContent.textCursor()
        content = unicode(self.textContent.toPlainText())
        contentSample = content[samplePosStart:samplePosEnd]

        if not contentSample or unicode.isspace(contentSample[0]):
            cursor.clearSelection()
            self.textContent.setTextCursor(cursor)
            return

        contentSampleFlat = contentSample.replace('\n', unicode())
        self.state.definitions, lengthMatched = self.language.findTerm(contentSampleFlat)

        sentence = reader_util.findSentence(content, samplePosStart)
        for definition in self.state.definitions:
            definition['sentence'] = sentence

        self.updateDefinitions()

        lengthSelect = 0
        if lengthMatched:
            for c in contentSample:
                lengthSelect += 1
                if c != '\n':
                    lengthMatched -= 1
                if lengthMatched <= 0:
                    break

        cursor.setPosition(samplePosStart, QtGui.QTextCursor.MoveAnchor)
        cursor.setPosition(samplePosStart + lengthSelect, QtGui.QTextCursor.KeepAnchor)
        self.textContent.setTextCursor(cursor)


    def clearArchiveFiles(self):
        self.menuOpenArchive.clear()
        self.menuOpenArchive.setEnabled(False)


    def updateArchiveFiles(self, filename, names):
        self.menuOpenArchive.setEnabled(True)
        for name in self.formatQStringList(names):
            index, ok = self.getItemIndex(name)
            if ok:
                index = index - 1
                self.menuOpenArchive.addAction(name, lambda fn=filename, idx=index: self.openFileInArchive(fn, idx))
            else:
                self.menuOpenArchive.addAction(name, lambda fn=filename: self.openFile(fn))


    def openFileInArchive(self, filename, index):
        self.state.scanPosition = 0
        self.state.archiveIndex = index
        self.openFile(filename)


    def clearRecentFiles(self):
        self.preferences.clearRecentFiles()
        self.updateRecentFiles()


    def updateRecentFiles(self):
        self.menuOpenRecent.clear()

        filenames = self.preferences.recentFiles()
        if len(filenames) == 0:
            return

        for filename in filenames:
            self.menuOpenRecent.addAction(filename, lambda f=filename: self.openFile(f))

        self.menuOpenRecent.addSeparator()
        self.menuOpenRecent.addAction('Clear file history', self.clearRecentFiles)


    def updateRecentFile(self, addIfNeeded=True):
        if self.state.filename:
            if addIfNeeded or self.state.filename in self.preferences.recentFiles():
                self.preferences.updateRecentFile(self.state.filename, self.state.scanPosition)


    def updateDefinitions(self):
        html = reader_util.buildDefinitionsHtml(self.state.definitions, self.ankiIsFactValid, 'vocab')
        self.textDefinitions.setHtml(html)


    def setStatus(self, status):
        self.statusBar.showMessage(status)
