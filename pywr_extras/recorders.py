from pywr.recorders import Recorder


class MetaRecorder(Recorder):
    def __init__(self, model, recorders=None, **kwargs):
        super(MetaRecorder, self).__init__(model, **kwargs)
        self.recorders = recorders

    def value(self, aggregate=True):

        data = []

        recorders = self.recorders
        if recorders is None:
            recorders = self.model.recorders

        for r in recorders:
            if isinstance(r, MetaRecorder):
                # Avoid recursion
                continue

            rdata = {
                'class': r.__class__.__name__,
                'name': r.name
            }

            try:
                rdata['value'] = r.value(aggregate=True)
            except NotImplementedError:
                pass

            try:
                rdata['node'] = r.node.name
            except AttributeError:
                pass

            try:
                rdata['all_values'] = list(r.value(aggregate=False))
            except AttributeError:
                pass

            data.append(rdata)

        return data


class JsonMetaRecorder(MetaRecorder):
    def value(self):
        import json
        return json.dumps(super(JsonMetaRecorder, self).value(), indent=4)