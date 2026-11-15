import retico_core


msg = []


def text_candidate_callback(update_msg):
    global msg

    for x, ut in update_msg:
        if ut == retico_core.UpdateType.ADD:
            msg.append(x)

        if ut == retico_core.UpdateType.REVOKE and x in msg:
            msg.remove(x)

    txt = ""
    committed = False
    for x in msg:
        txt += x.text + " "
        committed = committed or x.committed

    if committed:
        msg = []
        print("\nCommitted: " + txt)
    else:
        print("\rlive: " + txt, end="")
