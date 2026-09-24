"""Legacy live-order diagnostic disabled after credential removal."""


def main():
    raise RuntimeError(
        "Legacy live-order diagnostic disabled: credentials were removed; "
        "no real order path is available from this script."
    )


if __name__ == "__main__":
    main()
