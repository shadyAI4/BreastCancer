from datetime import datetime
import os
import cv2
import numpy as np
from PIL import Image
import streamlit as st
import argparse
import tensorflow as tf
from tensorflow.keras.models import load_model

from tortoise import Tortoise, fields, models
import asyncio

# most of this code has been obtained from Datature's prediction script
# https://github.com/datature/resources/blob/main/scripts/bounding_box/prediction.py

class ImagePrediction(models.Model):
    id = fields.IntField(pk=True)
    uploaded_image_path = fields.CharField(max_length=255)
    output_image_path = fields.CharField(max_length=255)
    class_detected = fields.CharField(max_length=255)
    score = fields.FloatField()
    created_at = fields.DatetimeField(auto_now_add=True)

async def init():
    await Tortoise.init(
        db_url='sqlite://database.sqlite3',
        modules={'models': ['__main__']}
    )
    await Tortoise.generate_schemas()

asyncio.run(init())

# Function to save prediction to the database
async def save_prediction(uploaded_image_path, output_image_path, class_detected, score):
    print("Saving prediction to the database", uploaded_image_path)
    prediction = await ImagePrediction.create(
        uploaded_image_path=uploaded_image_path,
        output_image_path=output_image_path,
        class_detected=class_detected,
        score=score
    )
    return prediction

def save_image(image, folder="images", prefix="image"):
    if not os.path.exists(folder):
        os.makedirs(folder)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    path = os.path.join(folder, filename)
    image.save(path)
    return path


st.set_option('deprecation.showfileUploaderEncoding', False)

# def args_parser():
#     parser = argparse.ArgumentParser(
#         description="Datature Open Source Prediction Script")
#     parser.add_argument(
#         "--input",
#         help="../input",
#         required=True,
# 		default="../input/"
#     )
#     parser.add_argument(
#         "--output",
#         help="../output",
#         required=True,
# 		default="../output/",
#     )
#     parser.add_argument(
#         "--model",
#         help="../saved_model/",
#         required=True,
# 		default="../saved_model",
#     )
#     parser.add_argument(
#         "--label",
#         help="../label_map.pbtxt",
#         required=True,
# 		default="../label_map.pbtxt",
#     )
#     parser.add_argument("--width",
#                         help=640,
#                         default=640)
#     parser.add_argument("--height",
#                         help=640,
#                         default=640)
#     parser.add_argument("--threshold",
#                         help=0.7,
#                         default=0.7)

#     return parser.parse_args()

def load_label_map(label_map_path):

    label_map = {}

    with open(label_map_path, "r") as label_file:
        for line in label_file:
            if "id" in line:
                label_index = int(line.split(":")[-1])
                label_name = next(label_file).split(":")[-1].strip().strip('"')
                label_map[label_index] = {"id": label_index, "name": label_name}
    return label_map
	
def predict_class(image, model):
	image = tf.cast(image, tf.float32)
	image = tf.image.resize(image, [640, 640])
	image = np.expand_dims(image, axis = 0)
	return model.predict(image)

def plot_boxes_on_img(color_map, classes, bboxes, image_origi, origi_shape):
	for idx, each_bbox in enumerate(bboxes):
		color = color_map[classes[idx]]

		
		cv2.rectangle(
			image_origi,
			(int(each_bbox[1] * origi_shape[1]),
			 int(each_bbox[0] * origi_shape[0]),),
			(int(each_bbox[3] * origi_shape[1]),
			 int(each_bbox[2] * origi_shape[0]),),
			color,
			2,
		)
		
		cv2.rectangle(
			image_origi,
			(int(each_bbox[1] * origi_shape[1]),
			 int(each_bbox[2] * origi_shape[0]),),
			(int(each_bbox[3] * origi_shape[1]),
			 int(each_bbox[2] * origi_shape[0] + 15),),
			color,
			-1,
		)
		## Insert label class & score
		cv2.putText(
			image_origi,
			"Class: {}, Score: {}".format(
				str(category_index[classes[idx]]["name"]),
				str(round(scores[idx], 2)),
			),
			(int(each_bbox[1] * origi_shape[1]),
			 int(each_bbox[2] * origi_shape[0] + 10),),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.3,
			(0, 0, 0),
			1,
			cv2.LINE_AA,
		)
	return image_origi

@st.cache_resource
def load_model(model_path):
	return tf.saved_model.load(model_path)
st.markdown(
    """
    <style>
    .sidebar .sidebar-content {
        background-color: #0077b6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.set_option('deprecation.showfileUploaderEncoding', False)

st.image('../breast_cancer.jpeg')

st.title('Breast Cancer Detection From UTRASOUND IMAGES')

file = st.sidebar.file_uploader("Choose image to evaluate model", type=["jpg", "png"])

button = st.sidebar.button('Detect Breast Cancer!')

# args = args_parser()

model = load_model("../saved_model")

if  button and file:

	st.text('Running inference...')
	# open image
	test_image = Image.open(file).convert("RGB")
	origi_shape = np.asarray(test_image).shape
	# resize image to default shape
	image_resized = np.array(test_image.resize((640, 640)))

	# Save the uploaded image
	uploaded_image_path = save_image(test_image, prefix="uploaded")
    
	## Load color map
	category_index = load_label_map("../label_map.pbtxt")

	# TODO Add more colors if there are more classes
  # color of each label. check label_map.pbtxt to check the index for each class
	color_map = {
		1: [255, 0, 0], # bad -> red
		2: [0, 255, 0] # good -> green
	}

	## The model input needs to be a tensor
	input_tensor = tf.convert_to_tensor(image_resized)
	## The model expects a batch of images, so add an axis with `tf.newaxis`.
	input_tensor = input_tensor[tf.newaxis, ...]

	## Feed image into model and obtain output
	detections_output = model(input_tensor)
	# print("model output",detections_output)
	num_detections = int(detections_output.pop("num_detections"))
	detections = {key: value[0, :num_detections].numpy() for key, value in detections_output.items()}
	detections["num_detections"] = num_detections

	## Filter out predictions below threshold
	# if threshold is higher, there will be fewer predictions
	# TODO change this number to see how the predictions change
	indexes = np.where(detections["detection_scores"] > 0.2)

	## Extract predicted bounding boxes
	bboxes = detections["detection_boxes"][indexes]
	# there are no predicted boxes
	if len(bboxes) == 0:
		st.error('No boxes predicted')
	# there are predicted boxes
	else:
		st.success('Image detected')
		print("This is the length", len(bboxes))
		classes = detections["detection_classes"][indexes].astype(np.int64)
		scores = detections["detection_scores"][indexes]
		print("This are tge clasess",category_index[classes[0]]['name'])
		# print("This are tge clasess",category_index[classes[1]]['name'])
		print("This are the score", scores)

		# plot boxes and labels on image
		image_origi = np.array(Image.fromarray(image_resized).resize((origi_shape[1], origi_shape[0])))
		image_origi = plot_boxes_on_img(color_map, classes, bboxes, image_origi, origi_shape)

		output_image = Image.fromarray(image_origi)
		output_image_path = save_image(output_image, prefix="output")

		# show image in web page
		st.image(Image.fromarray(image_resized), caption="Image with predictions", width=400)
		st.markdown("### Model output")
		class_detected =[]
		for idx in range(len((bboxes))):
			class_detected.append(category_index[classes[idx]]['name'])
			# st.markdown(f"* Class: {str(category_index[classes[idx]]['name'])}, confidence score: {str(round(scores[idx], 2))}")
		
		if("benign" in class_detected and "benign"==class_detected[0]):
			st.success(" Image contain a Benign tumor which is not cancerous.")
		else:
			st.error("Image contain a malignant tumor which is cancerous.")
   
		# Save prediction to the database
		asyncio.run(save_prediction(uploaded_image_path, output_image_path, class_detected[0], float(scores[0])))
