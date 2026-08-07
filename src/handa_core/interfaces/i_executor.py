class IExecutor:
    def execute(self, order, approved: bool):
        raise NotImplementedError
