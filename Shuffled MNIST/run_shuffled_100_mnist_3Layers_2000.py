import os
import sys

import numpy as np
import torch
import torch.nn as nn
import torchvision.datasets as dsets
import torchvision.transforms as transforms
from torch.autograd import Variable
from OWMLayer import OWMLayer

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # ignore warning
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # use gpu

# Seed
seed_num = 30
np.random.seed(seed_num)
torch.manual_seed(seed_num)
if torch.cuda.is_available():
    torch.cuda.manual_seed(seed_num)
else:
    print('[CUDA unavailable]')
    sys.exit()
# Hyper Pameters
class_num = 10  # mnist
num_epochs = 20
batch_size = 100
learning_rate = 2.0
dtype = torch.cuda.FloatTensor  # run on GPU
# MNIST Dataset
train_dataset = dsets.MNIST(root='./data/', train=True, transform=transforms.ToTensor(), download=True)

test_dataset = dsets.MNIST(root='./data/', train=False, transform=transforms.ToTensor())

# Data Loader (Input Pipeline)
train_loader = torch.utils.data.DataLoader(dataset=train_dataset, batch_size=batch_size, shuffle=True)

test_loader = torch.utils.data.DataLoader(dataset=test_dataset, batch_size=256, shuffle=True)


def get_weight(shape, zeros=None):
    np.random.seed(seed_num)
    if zeros is None:
        w = np.random.normal(0, 1.0, shape)
        w = torch.from_numpy(w/(np.sqrt(sum(shape)/2.0)))
    else:
        w = np.zeros(shape)
        w = torch.from_numpy(w)
    return Variable(w.type(dtype), requires_grad=True)


def get_bias(shape):
    bias = 0.01 * np.random.rand(shape)
    bias = torch.from_numpy(bias)
    return Variable(bias.type(dtype), requires_grad=True)


def get_layer(shape, alpha=1.0, zeros=None):
    """
    :type alpha: learningrate
    """
    w = get_weight(shape, zeros)
    return w, OWMLayer(shape, alpha)



# Layer1
w1, force_layer1 = get_layer([28*28, 2000])
b1 = get_bias(w1.size(1))
# Layer2
w2, force_layer2 = get_layer([2000, 2000])
b2 = get_bias(w2.size(1))
# Layer_out
wo, force_layer_out = get_layer([2000, class_num])
myAFun = nn.ReLU().cuda()
myDrop = nn.Dropout(p=0.05).cuda()
criterion = nn.CrossEntropyLoss().cuda()
n = 0
lambda_loss = 1e-4
Task_num = 100


# Test the Model
def my_test(test_Task_num=0):
    correct_all = []
    for task_index in range(test_Task_num+1):
        ss = np.arange(28 * 28)
        if task_index > 0:
            np.random.seed(task_index)
            np.random.shuffle(ss)
        correct = 0
        total = 0
        for i, (images, labels) in enumerate(test_loader):
            if i > 9:
                break
            images = Variable(images).cuda()
            images = images.view(-1, 28 * 28)
            numpy_data = images.data.cpu().numpy()
            input = torch.from_numpy(numpy_data[:, ss])
            input = Variable(input.type(dtype))
            # Forward
            output1 = myAFun(input.mm(w1) + b1)

            output2 = myAFun(output1.mm(w2) + b2)

            y_pred = output2.mm(wo)

            _, predicted = torch.max(y_pred.data, 1)
            total += labels.size(0)
            correct += (predicted.cpu() == labels).sum()
        correct_all.append((100 * correct / total))
        # print('Test Accuracy of the model on the 10000 Shuffled_mnist images: %0.2f %%' % (100 * correct / total))
    this_acc = sum(correct_all) / len(correct_all)
    # print("Average Test Accuracy on Previous All Tasks: {0:.2f} %".format(this_acc))
    return this_acc


test_array = []
for task_index in range(Task_num):
    ss = np.arange(28*28)
    if task_index > 0:
        np.random.seed(task_index)
        np.random.shuffle(ss)
    for epoch in range(num_epochs):
        for i, (images, labels) in enumerate(train_loader):
            lamda = i / (len(train_dataset) // batch_size)
            alpha_array = [1.0 * 0.0001 ** lamda, 1.0 * 0.1 ** lamda, 0.5]
            labels = Variable(labels).cuda()
            images = Variable(images).cuda()
            images = images.view(-1, 28 * 28)
            numpy_data = images.data.cpu().numpy()
            input = torch.from_numpy(numpy_data[:, ss])
            input = Variable(input.type(dtype))
            # Forward + Backward + Optimize
            output1 = myDrop(myAFun(input.mm(w1) + b1))

            output2 = myDrop(myAFun(output1.mm(w2) + b2))

            y_pred = output2.mm(wo)
            loss = criterion(y_pred, labels)+lambda_loss*(torch.norm(w1)+torch.norm(wo)+torch.norm(w2))
            loss.backward()

            force_layer1.force_learn(w1, input, learning_rate, alpha=alpha_array[0])
            force_layer2.force_learn(w2, output1, learning_rate, alpha=alpha_array[1])
            force_layer_out.force_learn(wo, output2, learning_rate, alpha=alpha_array[2])

            # n = torch.norm(wo).data[0]
            # if ((i + 1) % (len(train_dataset) // (batch_size) )) == 0:
            #     print('Task [{:d}/{:d}]: Epoch [{:d}/{:d}], Iter [{:d}/{:d}] Loss: {:.3f} Norm: {:.3f}'
            #           .format(task_index + 1, Task_num, epoch + 1, num_epochs, i + 1, len(train_dataset) // batch_size,
            #                   loss.data[0], n))

    test_array.append(my_test(task_index))
    print("Average Test Accuracy on Previous All Tasks: ", len(test_array))
    for ii in test_array:
        print("{:.2f} ".format(ii))
