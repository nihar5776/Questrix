# DATA STRUCTURES

## Sorting Techniques
Sorting techniques arrange data elements in a specific order (ascending or descending).
Bubble sort works by repeatedly swapping adjacent elements if they are in the wrong order. It has a time complexity of O(n^2).
Selection sort works by repeatedly finding the minimum element from the unsorted portion and placing it at the beginning. It maintains two sub-arrays in a given array.
Insertion sort builds the final sorted array one item at a time. It iterates, taking one element from the input data, and finds the location it belongs within the sorted list, and inserts it there.

## Linked List Implementation & Applications
A Linked List is a linear data structure where elements are stored in nodes, and each node contains a data field and a reference (link) to the next node.
Singly linked list allows traversal in one direction only. Common operations include insertion at head/tail/position, deletion of a node, reversing a linked list iteratively and recursively, and finding minimum and maximum elements in a linked list.
Linked lists can be used to represent polynomials, where each node stores the coefficient and exponent of a term, enabling polynomial addition.
Circular linked list is a variation where the last node points back to the first node (head), supporting insertion, deletion, and continuous traversal.
Doubly linked list allows traversal in both forward and backward directions as each node contains pointers to both the next and previous nodes, supporting bidirectional insertion and deletion.

## Stack Operations & Applications
A Stack is a linear data structure that follows the Last-In-First-Out (LIFO) principle.
Stack can be implemented using arrays or linked lists. Primary operations are push (insert element), pop (remove element), and peek/top.
Stack applications include evaluating postfix expressions, converting infix expressions to postfix expressions using operator precedence, checking for balanced parentheses in expressions, and checking if a string is a palindrome.
