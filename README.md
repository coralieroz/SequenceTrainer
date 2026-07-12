# Number-Sequence / Pattern Completion Drill
This game trains numerical pattern recognition to improve brain function and / or to help prepare for online assessments such as *Optiver*'s 26 in 25 or *SIG*'s quantitative evalutaion.

**How to use:** ensure you have flask installed:
```
py -m pip install flask
```
Run [run.py](run.py) and enter [http://127.0.0.1:5000](http://127.0.0.1:5000) into your browser of choice.  User data is stored locally in CSV files so progress can be tracked in real-time.  To end the running, simply type ```Ctrl+C``` into the terminal.  The differences between the two branches are outlined below.

### *main* branch
Runs sequences of length 9 so that interleaved sequences can use quadratic and fibonacci sequences.
### *SeriesLengthChange* branch
Runs sequences of length 7 since sequences of length 9 end up with ridiculous terms and most online assessments use 7 terms anyway.  Runs the risk of being a little simpler (less mental maths required) and interleaved sequences can only use arithmetic and geometric sequences.

I'm ultimately still waiting on feedback as to which option is better, so in the meantime, feel free to choose whichever you prefer for practise.
