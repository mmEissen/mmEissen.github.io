Declarative Circuit Language
============================

I want to declare circuits by defining their components and the connections. Then I want to be able to turn that into a circuit diagram automagically. The circuit diagram should be optimized to "look good". This means short connections, few crossings, and straight lines.

Ultimately I want to define circuits in ``*.rst`` files and have a Sphinx extention do the rest for me.

The Solver
----------

The solver is the hardest part of this and what I am tackling first. The layouting can be modeled as a constraint satisfaction problem. The requirement "short connections, few crossings, and straight lines" is an optimization variable. Since I have used it before, I will attempt to use ortools to solve the constraint optimization.

Firstly, everything will be on a grid. Components are rectangular. They may have ports only on their edges. A port may be connected to one or more other ports, not necessarily from different components. Wires follow the grid.

Modeling
````````

I modeled the components as 4 ``IntVars`` s: The bottom left x coordinate 
(:math:`x_{ll}`), the bottom left y coordinate (:math:`y_{ll}`), one boolean whether the component is rotated by 180 degrees (:math:`f` for flip), and one boolean whether the component is rotated by an additional 90 degrees (:math:`r` for rotate). Note that "bottom left" is always an absolute term, *not* dependant on the rotation of the component.

Additionally I define some constants. All of these should be interpreted in the local, rotated coordinates of the component.
    - :math:`w`: the width of the component
    - :math:`h`: the height of the component
    - :math:`p_{i,x}`: the x position of port i, relative to :math:`x_{ll}`
    - :math:`p_{i,y}`: the y position of port i, relative to :math:`y_{ll}`

My initial idea is to have two phases:
    #. Placing the components
    #. Connecting the wires

To solve the first phase I shall define some additional ``IntExpr`` s for the upper right coordinates:
    - :math:`x_{ur} = \underbrace{(1-r)(x_{ll}+w)}_{\text{if not rotated}} + \underbrace{(r)(x_{ll}+h)}_{\text{if rotated}}`
    - :math:`y_{ur} = \underbrace{(1-r)(y_{ll}+h)}_{\text{if not rotated}} + \underbrace{(r)(y_{ll}+w)}_{\text{if rotated}}`

For every pair of different components I can then declare constraints to make them not overlap.
