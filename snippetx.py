import os
import re
import sublime
import sublime_plugin
import xml.etree.ElementTree as ET


class snippetxCommand(sublime_plugin.TextCommand):

    def getFields(self, lines):
        for line in lines:
            # for escape comma feature START
            result_line = []
            while True:
                r = re.search(r'[^\\](,)', line)
                if r:
                    field = line[:r.end()-1]
                    field = field.replace('\\,', ',')
                    result_line.append(field)
                    line = line[r.end():]
                else:
                    result_line.append(line.replace('\\,', ','))
                    break
            # for escape comma feature END
            yield result_line

    def findFiles(self, path, type=".sublime-snippet"):
        all_snippet_path = []
        for root, dirs, files in os.walk(path):
            # skip some "hidden" directories like .git, .svn, and node_modules.
            if '/.' in root or '/node_modules' in root:
                continue
            for file_name in files:
                if file_name.endswith(type):
                    all_snippet_path.append(os.path.join(root, file_name))
        return all_snippet_path

    def xmlMatchTabTrigger(self, paths, trigger_name):
        for path in paths:
            try:
                xml_root = ET.parse(path)
                tabTrigger_node = xml_root.find('tabTrigger')
                if str(tabTrigger_node.text) == trigger_name:
                    print("trigger_name: %s" % trigger_name)
                    yield xml_root
            except Exception as e:
                print("xmlMatchTabTrigger got: {e} @ {path}".format(e=e, path=path,))
                continue

    def zipSnip(self, snippet, fields, indent=''):
        snippet = snippet.strip()
        for idx, field in enumerate(fields):
            snippet = re.sub(r'(?<!\\)\${{{0}:.*?}}|\${0}'.format(str(idx+1)), field, snippet)
        snippet = re.sub(r'(?<!\\)\$\{\d+:(.+?)\}', '\\1', snippet)
        snippet = re.sub(r'(?<!\\)\$\d+', '', snippet)
        return indent + snippet

    def getMatch(self, pattern, num):
        return self.view.substr(self.view.find(pattern, num))

    def checkScope(self, present, allowed):
        for scope in present:
            for allow in allowed:
                if re.match(scope.strip(), allow):
                    return True
        return False

    def filterByScope(self, snippet_xml, allowed):
        scope_node = snippet_xml.find('scope')
        if scope_node is None:
            return True
        scope_text = snippet_xml.find('scope').text
        print("snippet_xml.find('scope').text: %s" % str(snippet_xml.find('scope').text))
        scope_rmNeg = re.sub(r'- .*? ', '', scope_text)
        return self.checkScope(scope_rmNeg.split(','), allowed)

    def getData(self, pattern):
        csv_lines = self.getMatch(pattern, 0).splitlines()

        assert csv_lines
        print("csv_lines: %s" % csv_lines)
        csv_lines = list(filter(lambda x: x.strip(), csv_lines))
        snippet_name = ''
        for i in [0, -1]:
            if 'sx:' in csv_lines[i]:
                snippet_name = csv_lines.pop(i).split('sx:')[-1]

        return {
            '+metaRegion': self.view.find(pattern, 0),
            'snippetName': snippet_name,
            'indent': re.findall(r'^[\t\s]*', csv_lines[0])[0],
            'asLinesMassaged': [
                re.sub(r'(^[\t\s]*|["]*)*', '', content)
                for content in csv_lines if content.strip()
            ],
        }

    def getSnippet(self, name=None, scope=['text.plain']):
        
        filenames = self.findFiles(sublime.packages_path())
        snippet_xmls = self.xmlMatchTabTrigger(filenames, str(name))
        snippet_contents = [
            x.find('content').text
            for x in snippet_xmls
            if self.filterByScope(x, scope)
        ]
        return snippet_contents

    def run(self, edit):

        patterns = r"([\t ]*sx:.*[\n\r]*)(.+[\n\r]?)*|(?<=[\n\r])?(.+[\n\r])+([\t ]*sx:.+)"

        data = self.getData(patterns)

        if (data['+metaRegion'].a >= 0 and data['+metaRegion'].b > 0):
            scope = self.view.scope_name(data['+metaRegion'].a).split(' ')

            snippets = self.getSnippet(data['snippetName'], scope)

            if snippets:
                self.view.replace(edit, data['+metaRegion'], '')

                for snippet in snippets:
                    snips = '\n'.join(
                        self.zipSnip(snippet, fields, data['indent'])
                        for fields in self.getFields(data['asLinesMassaged'])
                    )
                    self.view.insert(edit, data['+metaRegion'].a, snips)
            else:
                sublime.status_message("Can't find snippet trigger by %s" % data['snippetName'])

        else:
            sublime.status_message("Can't find region.")
