1	Customer Places Order	pending_tailor_acceptance	pending / partially_paid
2	Tailor Accepts	awaiting_pickup	(no change)
3	Partner Dispatched	pickup_in_progress	(no change)
4	Partner Collects Fabric	fabric_collected	(no change)
5	Fabric Reaches Tailor	in_progress	(no change)
6	Tailor Finishes	ready_for_delivery	(no change)
7	Partner Picks Up Garment	out_for_delivery	(no change)
8	Customer Receives Item	completed	fully_paid

flask db init
flask db migrate -m  " message"
flask db upgrade

$env:FLASK_APP = "run.py"