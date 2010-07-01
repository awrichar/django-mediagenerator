from hashlib import sha1
from .utils import _load_backend, _find_file

class Filter(object):
    takes_input = True

    def __init__(self, **kwargs):
        self.file_filter = FileFilter
        self.config(kwargs, filetype=None, filter=None)

        # We assume that if this is e.g. a 'js' backend then all input must
        # also be 'js'. Subclasses must override this if they expect a special
        # input file type. Also, subclasses have to check if their file type
        # is supported.
        self.input_filetype = self.filetype

        if self.takes_input:
            self.config(kwargs, input=())
            if not isinstance(self.input, (tuple, list)):
                self.input = (self.input,)
        self._input_filters = None
        assert not kwargs, 'Unknown parameters: %s' % ', '.join(kwargs.keys())

    def get_variations(self):
        """
        Returns all possible variations that get generated by this filter.

        The result must be a dict whose values are tuples.
        """
        return {}

    def get_output(self, variation):
        """
        Yields file-like objects with content for each output item for the
        given variation.
        """
        raise NotImplementedError()

    def get_dev_output(self, name, variation):
        """
        Returns content for the given file name and variation in development mode.
        """
        index, child = name.split('/', 1)
        index = int(index)
        filter = self.get_input_filters()[index]
        return filter.get_dev_output(child, variation)

    def get_dev_output_names(self, variation):
        """
        Yields file names for the given variation in development mode.
        """
        # By default we simply return our input filters' file names
        for index, filter in enumerate(self.get_input_filters()):
            for name in filter.get_dev_output_names(variation):
                yield '%d/%s' % (index, name)

    def get_input(self, variation):
        """Yields contents for each input item."""
        for filter in self.get_input_filters():
            for input in filter.get_output(variation):
                yield input

    def get_input_filters(self):
        """Returns a Filter instance for each input item."""
        if not self.takes_input:
            raise ValueError("The %s media filter doesn't take any input" %
                             self.__class__.__name__)
        if self._input_filters is not None:
            return self._input_filters
        self._input_filters = []
        for input in self.input:
            if isinstance(input, dict):
                filter = self.get_filter(input)
            else:
                filter = self.get_item(input)
            self._input_filters.append(filter)
        return self._input_filters

    def get_filter(self, config):
        backend_class = _load_backend(config.get('filter'))
        return backend_class(filetype=self.input_filetype, **config)

    def get_item(self, name):
        return self.file_filter(name=name, filetype=self.input_filetype)

    def _get_variations_with_input(self):
        """Utility function to get variations including input variations"""
        variations = self.get_variations()
        if not self.takes_input:
            return variations

        for filter in self.get_input_filters():
            subvariations = filter.get_variations()
            for k, v in subvariations.items():
                if k in variations and v != variations[k]:
                    raise ValueError('Conflicting variations for "%s": %r != %r' % (
                        k, v, variations[k]))
            variations.update(subvariations)
        return variations

    def config(self, init, **defaults):
        for key in defaults:
            setattr(self, key, init.pop(key, defaults[key]))

class FileFilter(Filter):
    """A filter that just returns the given file."""
    takes_input = False

    def __init__(self, **kwargs):
        self.config(kwargs, name=None)
        super(FileFilter, self).__init__(**kwargs)

    def get_output(self, variation):
        yield self.get_dev_output(self.name, variation)

    def get_dev_output(self, name, variation):
        name = name.split('/', 1)[-1]
        assert name == self.name, "File name doen't match the one in GENERATE_MEDIA"
        path = _find_file(name)
        assert path, """File name "%s" doesn't exist.""" % name
        fp = open(path, 'r')
        output = fp.read()
        fp.close()
        return output

    def get_dev_output_names(self, variation):
        output = self.get_dev_output('hash/%s' % self.name, variation)
        hash = sha1(output).hexdigest()
        yield '%s/%s' % (hash, self.name)
