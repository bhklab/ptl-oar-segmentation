from __future__ import absolute_import
from collections import OrderedDict
from torch import nn

# from .bn import ABN

class IdentityResidualBlock(nn.Module):
    def __init__(self,
                 in_channels,
                 channels,
                 stride=1,
                 dilation=1,
                 groups=1,
                 norm_act=True,
                 dropout=None):

        """Configurable identity-mapping residual block
        Parameters
        ----------
        in_channels : int
            Number of input channels.
        channels : list of int
            Number of channels in the internal feature maps. Can either have two or three elements: if three construct
            a residual block with two `3 x 3` convolutions, otherwise construct a bottleneck block with `1 x 1`, then
            `3 x 3` then `1 x 1` convolutions.
        stride : int
            Stride of the first `3 x 3` convolution
        dilation : int
            Dilation to apply to the `3 x 3` convolutions.
        groups : int
            Number of convolution groups. This is used to create ResNeXt-style blocks and is only compatible with
            bottleneck blocks.
        norm_act : callable
            Function to create normalization / activation Module.
        dropout: callable
            Function to create Dropout Module.
        """
        super(IdentityResidualBlock, self).__init__()

        # Check parameters for inconsistencies
        if len(channels) != 2 and len(channels) != 3:
            raise ValueError("channels must contain either two or three values")
        if len(channels) == 2 and groups != 1:
            raise ValueError("groups > 1 are only valid if len(channels) == 3")

        is_bottleneck = len(channels) == 3
        need_proj_conv = stride != 1 or in_channels != channels[-1]

        self.bn1 = nn.Sequential(nn.BatchNorm3d(in_channels),
                                 nn.PReLU(in_channels))
        if not is_bottleneck:
            layers = [
                ("conv1", nn.Conv3d(in_channels, channels[0], 3, stride=stride, padding=dilation, bias=False,
                                    dilation=dilation)),
                ("bn2", nn.BatchNorm3d(channels[0])),
                ("pr2", nn.PReLU(channels[0])),
                ("conv2", nn.Conv3d(channels[0], channels[1], 3, stride=1, padding=dilation, bias=False,
                                    dilation=dilation))
            ]
            if dropout is not None:
                layers = layers[0:2] + [("dropout", dropout())] + layers[2:]
        else:
            layers = [
                ("conv1", nn.Conv3d(in_channels, channels[0], 1, stride=stride, padding=0, bias=False)),
                ("bn2", nn.BatchNorm3d(channels[0])),
                ("pr2", nn.PReLU(channels[0])),
                ("conv2", nn.Conv3d(channels[0], channels[1], 3, stride=1, padding=dilation, bias=False,
                                    groups=groups, dilation=dilation)),
                ("bn2", nn.BatchNorm3d(channels[1])),
                ("pr2", nn.PReLU(channels[1])),
                ("conv3", nn.Conv3d(channels[1], channels[2], 1, stride=1, padding=0, bias=False))
            ]
            if dropout is not None:
                layers = layers[0:4] + [("dropout", dropout())] + layers[4:]

        self.convs = nn.Sequential(OrderedDict(layers))

        if need_proj_conv:
            self.proj_conv = nn.Conv3d(in_channels, channels[-1], 1, stride=stride, padding=0, bias=False)

    def forward(self, x):
        if hasattr(self, "proj_conv"):
            bn1 = self.bn1(x)
            shortcut = self.proj_conv(bn1)
        else:
            shortcut = x.clone()
            bn1 = self.bn1(x)

        out = self.convs(bn1)
        out.add_(shortcut)

        return out
