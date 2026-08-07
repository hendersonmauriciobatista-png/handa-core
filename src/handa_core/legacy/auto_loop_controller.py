class AutoLoopController:
    def __init__(self, auto_loop, logger):
        self.auto_loop = auto_loop
        self.logger = logger

    def start(self):
        if self.auto_loop.is_running:
            self.logger.log("AUTO LOOP já está em execução.")
            return

        self.auto_loop.start()
        self.logger.log("AUTO LOOP iniciado.")
