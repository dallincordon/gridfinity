To start, I made some sample 1 x 1 gridfinity boxes at different heights (3–6U) and made labels for each. Here is the code I used to generate them:

```bash
gflabel cullenect "3U" --font-style bold --margin 1 -o 3u_label.step
```

## Fasteners

### SAE

SHCS Hex-Drive # 4-40 3/8
```bash
gflabel cullenect "{2}{head(hex)} {bolt(9.525, socket)}{...}\n#4-40×3/8\"" --font-style bold
```

In bambustudio, I managed to add a second slash with the text shape using free sans as the font, a size of 5.5, and a thickness of 0.4 

### Metric

I tried the following approach:
```bash
gflabel cullenect "{head(hex)} {bolt(8, socket)}\nM3×8" --font-style bold -o m3-8_cap_hex.step
```
but the sizing of the hex drive head was too small to be readable. If I want a hex-head graphic, it can’t be squeezed into a row—it’ll need to run the full height of the label.

This is getting me closer:
```bash
gflabel cullenect "{head(hex)}{|}{cullbolt(socket)}{1|2}M3\n×8" --font-style bold -o m3_test.step
```

But I think this is the best so far:
```
gflabel cullenect "{head(hex)}{3|4}{cullbolt(flipped,socket)}{1|2}M3\n×8" --font-style bold --margin 0 -o m3_test.step
```

In the end, I printed that, but it doesn't look as good as the cullenect bolt. So I'm going with this:
```bash
gflabel cullenect "{cullbolt(flipped,socket,hex)}{1|1}M3\n×8" --font-style bold --margin 0 -o m3_test_cull.step
```


## Nuts and Washers

For a nut, I decided to go simple with:
```bash
 gflabel cullenect "{<}{nut}{1|2}M5\n" --font-style bold --margin 0 -o m5_nut.step
```

I'll leave the second row to specify anything if there is any distinguishing element that separates it from a normal nut (e.g., locking, acorn, square, low-profile, etc.)

For a washer, I went with:
```bash
gflabel cullenect "{<}{washer}{1|2}M5\n" --font-style bold --margin 0 -o m5_washer.step
```

Both the nut and washer are small enough to use a {1|2} approach to give more space for specifying information like inner and outer diameter and thickness for the washer

For a lockwasher:
```bash
gflabel cullenect "{<}{lockwasher}{1|2}M5\n" --font-style bold --margin 0 -o m5_lockwasher.step
```

