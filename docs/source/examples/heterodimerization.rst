Heterodimerization (intro example)
==================================

We can initialize a system of a simple reversable binding interaction as follows:

.. code-block::

    from kappybara.system import System

    system = System.from_kappa(
        mixture={"A(x[.])": 100, "B(x[.])": 100},
        rules=[
            "A(x[.]), B(x[.]) -> A(x[1]), B(x[1]) @ 1",
            "A(x[1]), B(x[1]) -> A(x[.]), B(x[.]) @ 1",
        ],
        observables={"AB": "|A(x[1]), B(x[1])|"},
    )

or equivalently from a .ka-style string:

.. code-block::

    system = System.from_ka(
        """
        %init: 100 A(x[.])
        %init: 100 B(x[.])

        %obs: 'AB' |A(x[1]), B(x[1])|

        A(x[.]), B(x[.]) <-> A(x[1]), B(x[1]) @ 1, 1
        """
    )

100 instances of molecules of type ``A`` and of type ``B``, each with an empty binding domain ``x`` are created, and we track the number of ``AB`` complexes.

We're going to simulate this system and plot its behavior, marking certain times of interest.
We'll first simulate until time 1:

.. code-block::

    times = []
    while system.time < 1:
        system.update()
    times.append(system.time)

We'll now manually instantiate 50 new ``A`` and ``B`` molecules each, start tracking the number of free ``A``, and simulate until there are no more than 10 free ``A`` in the mixture:

.. code-block::
    
    from kappybara.pattern import Pattern

    system.mixture.instantiate("A(x[.]), B(x[.])", 50)

    system["A"] = "|A(x[.])|"
    while system["A"] > 10:
        system.update()
    times.append(system.time)

The default simulator provides the most features since it's written directly in Python, but models can be offloaded to `KaSim <https://github.com/Kappa-Dev/KappaTools>`__, a compiled Kappa simulator, for faster simulation.
For example:

.. code-block::

    system.update_via_kasim(time=1)

Finally, let's plot the history of the quantities we tracked:

.. code-block::

    import matplotlib.pyplot as plt

    system.monitor.plot()
    for time in times:
        plt.axvline(time, color="black", linestyle="dotted")
    plt.show()

.. image:: ../_static/heterodimerization-timeseries.png
    :width: 50%
    :align: center

Above it can be seen that the system equilibrates relatively early, new ``A`` is added and the number of complexes increases, and then observables are computed at the end of a period of computation in KaSim.
