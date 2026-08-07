def render_slot(slot_state):
    print(f"[{slot_state.slot_id}] {slot_state.status}")

    if slot_state.symbol:
        print(f"Par: {slot_state.symbol}")

    if slot_state.last_event:
        print(f"Evento: {slot_state.last_event}")

    if slot_state.error:
        print(f"⚠️ ERRO: {slot_state.error}")
