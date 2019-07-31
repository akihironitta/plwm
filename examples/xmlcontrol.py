
from os.path import split, join

try:
        # Python 2.5 bundled elementtree
        from xml.etree import ElementTree, ElementInclude
except ImportError:
        # Pre-2.5 third party elementtree
        from elementtree import ElementTree, ElementInclude


class XML_controller(dict):
    """Controller part of the MVC model for a user selection facility."""

    def __init__(self, node, actions):
        """Verify that everything is labeled and has an action."""

        for child in node:
            if not child.get('label'):
                raise ValueError, 'Element %s has no label' % child.tag
            if not actions.has_key(child.tag):
                raise ValueError, 'Element tag %s not in actions' % child.tag
            self[child.get('label')] = child
        self.actions = dict(actions)

    def choose(self, label):
        """Run the code that goes with labe."""

        self.actions[self[label].tag](self[label])

class Loader(object):
    """Custmom loader for XInclude processing to fix relative addressing."""

    def __init__(self, name):
        self.base = split(name)[0]

    def __call__(self, href, typ, encoding=None):
        """Fix relative references and call the default loader."""

        return ElementInclude.default_loader(join(self.base, href), typ, encoding)

def load_menus(path):
    """Load the file path."""

    menus = ElementTree.parse(path)
    ElementInclude.include(menus.getroot(), loader=Loader(path))
    return menus
