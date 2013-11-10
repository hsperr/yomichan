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


from PyQt4 import QtGui
import re


def decodeContent(content):
    encodings = ['utf-8', 'shift_jis', 'euc-jp', 'utf-16']
    errors = dict()

    for encoding in encodings:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError, e:
            errors[encoding] = e[2]

    encoding = sorted(errors, key=errors.get, reverse=True)[0]
    return content.decode(encoding, 'replace'), encoding


def stripContentReadings(content):
    return re.sub(u'《[^》]+》', unicode(), content)


def findSentence(content, position):
    quotesFwd = {u'「': u'」', u'『': u'』', u"'": u"'", u'"': u'"'}
    quotesBwd = {u'」': u'「', u'』': u'『', u"'": u"'", u'"': u'"'}
    terminators = u'。．.？?！!'

    quoteStack = list()

    start = 0
    for i in xrange(position, start, -1):
        c = content[i]

        if not quoteStack and (c in terminators or c in quotesFwd or c == '\n'):
            start = i + 1
            break

        if quoteStack and c == quoteStack[0]:
            quoteStack.pop()
        elif c in quotesBwd:
            quoteStack.insert(0, quotesBwd[c])

    quoteStack = list()

    end = len(content)
    for i in xrange(position, end):
        c = content[i]

        if not quoteStack:
            if c in terminators:
                end = i + 1
                break
            elif c in quotesBwd:
                end = i
                break

        if quoteStack and c == quoteStack[0]:
            quoteStack.pop()
        elif c in quotesFwd:
            quoteStack.insert(0, quotesFwd[c])

    return content[start:end].strip()


def replaceMarkupInFields(fields, markup):
    result = dict()
    for field, value in fields.items():
        result[field] = value.format(**markup)

    return result


def buildFactMarkupExpression(expression, reading, glossary, sentence=None):
    return {
        'expression': expression,
        'reading': reading,
        'glossary': glossary,
        'sentence': sentence
    }


def buildFactMarkupReading(reading, glossary, sentence=None):
    return {
        'expression': reading,
        'reading': unicode(),
        'glossary': glossary,
        'sentence': sentence
    }


def splitTags(tags):
    return filter(lambda tag: tag.strip(), re.split('[;,\s]', tags))


def copyDefinitions(definitions):
    text = unicode()

    for definition in definitions:
        if definition['reading']:
            text += u'{expression}\t{reading}\t{glossary}\n'.format(**definition)
        else:
            text += u'{expression}\t{meanings}\n'.format(**definition)

    QtGui.QApplication.clipboard().setText(text)


def buildDefinitionHtml(definition, factIndex, factQuery, profile):
    reading = unicode()
    if definition['reading']:
        reading = u'[{0}]'.format(definition['reading'])

    conjugations = unicode()
    if len(definition['rules']) > 0:
        conjugations = u' &bull; '.join(definition['rules'])
        conjugations = '<span class = "conjugations">&lt;{0}&gt;<br/></span>'.format(conjugations)

    links = '<a href = "copyDefinition:{0}"><img src = "://img/img/icon_copy_definition.png" align = "right"/></a>'.format(factIndex)
    if factQuery:
        if factQuery(profile, buildFactMarkupExpression(definition['expression'], definition['reading'], definition['glossary'])):
            links += '<a href = "addExpression:{0}"><img src = "://img/img/icon_add_expression.png" align = "right"/></a>'.format(factIndex)
        if factQuery(profile, buildFactMarkupReading(definition['reading'], definition['glossary'])):
            links += '<a href = "addReading:{0}"><img src = "://img/img/icon_add_reading.png" align = "right"/></a>'.format(factIndex)

    html = u"""
        <span class = "links">{0}</span>
        <span class = "expression">{1}&nbsp;{2}<br/></span>
        <span class = "glossary">{3}<br/></span>
        <span class = "conjugations">{4}</span>
        <br clear = "all"/>""".format(links, definition['expression'], reading, definition['glossary'], conjugations)

    return html


def buildDefinitionsHtml(definitions, factQuery, profile):
    palette = QtGui.QApplication.palette()
    toolTipBg = palette.color(QtGui.QPalette.Window).name()
    toolTipFg = palette.color(QtGui.QPalette.WindowText).name()

    html = u"""
        <html><head><style>
        body {{ background-color: {0}; color: {1}; font-size: 11pt; }}
        span.expression {{ font-size: 15pt; }}
        </style></head><body>""".format(toolTipBg, toolTipFg)

    if len(definitions) > 0:
        for i, definition in enumerate(definitions):
            html += buildDefinitionHtml(definition, i, factQuery, profile)
    else:
        html += """
            <p>No definitions to display.</p>
            <p>Mouse over text with the <em>middle mouse button</em> or <em>shift key</em> pressed to search.</p>
            <p>You can also also input terms in the search box below.</p>"""

    html += '</body></html>'
    return html
