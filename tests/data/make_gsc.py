# Generates the fictional Sweat & Co Search Console sample used in Module 5.
B = "https://www.sweatandco.sg"
rows = [
("sweat and co", "/", 820, 2100, 1.1),
("sweat & co singapore", "/", 410, 1250, 1.2),
("sweat and co promo code", "/", 66, 480, 1.6),
("fithub vs sweat and co", "/", 11, 260, 3.9),
("adjustable dumbbells singapore", "/products/adjustable-dumbbells-24kg", 260, 9800, 4.3),
("adjustable dumbbells review", "/products/adjustable-dumbbells-24kg", 19, 2400, 9.7),
("dumbbells singapore", "/collections/dumbbells", 190, 14200, 6.8),
("buy dumbbells online singapore", "/collections/dumbbells", 74, 2300, 5.1),
("kettlebell singapore", "/collections/dumbbells", 52, 3700, 7.7),
("home gym equipment singapore", "/collections/dumbbells", 29, 6100, 13.5),
("yoga mat singapore", "/collections/yoga-mats", 310, 12600, 3.9),
("best yoga mat for beginners", "/collections/yoga-mats", 22, 4100, 11.4),
("yoga mat thickness guide", "/collections/yoga-mats", 6, 1700, 21.3),
("foldable treadmill singapore", "/products/foldable-treadmill-t200", 145, 8900, 5.6),
("treadmill for hdb", "/products/foldable-treadmill-t200", 61, 1900, 3.4),
("treadmill singapore", "/collections/treadmills", 98, 18400, 9.2),
("resistance bands singapore", "/collections/resistance-bands", 133, 5200, 4.0),
("how to use resistance bands", "/blog/how-to-use-resistance-bands", 88, 7600, 7.3),
("resistance band exercises", "/blog/how-to-use-resistance-bands", 41, 6900, 12.6),
("hdb home gym ideas", "/blog/hdb-home-gym-ideas", 156, 3400, 2.8),
("home gym singapore", "/blog/hdb-home-gym-ideas", 37, 11300, 14.1),
("home gym equipment singapore", "/blog/hdb-home-gym-ideas", 18, 3900, 15.8),
("what is the best home workout equipment", "/blog/hdb-home-gym-ideas", 9, 2200, 18.7),
("kettlebell workout for beginners", "/blog/kettlebell-workout-for-beginners", 64, 5800, 8.1),
("spin bike singapore", "/products/spin-bike-s1", 47, 4600, 8.9),
("exercise bike for home", "/products/spin-bike-s1", 12, 2900, 16.2),
("pull up bar singapore", "/collections/pull-up-bars", 83, 2600, 3.1),
("pull up bar no screws", "/collections/pull-up-bars", 35, 1500, 4.6),
("rowing machine vs treadmill", "/blog/rowing-machine-vs-treadmill", 58, 2700, 5.2),
("dumbbell delivery singapore", "/pages/delivery", 14, 640, 6.3),
]
print("query,page,clicks,impressions,ctr,position")
for q, p, c, i, pos in rows:
    print(f"{q},{B}{p},{c},{i},{round(c / i, 4)},{pos}")
